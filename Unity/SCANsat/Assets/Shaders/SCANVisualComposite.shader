// SCANsat "Visual" map mode, composited on the GPU.
//
// This is a full-screen Blit shader that reproduces the per-pixel Visual branch of
// SCANmap.getPartialMap (SCANmap.cs ~1011-1360). Rendering the Visual map here lets us
// sample the body's ORIGINAL ScaledSpace textures directly on the GPU, so SCANsat no
// longer needs a CPU-readable copy of them - the copy is what blows up RAM under RSS
// (4K-8K bodies -> hundreds of MB each). See SCANmap.tryRenderVisualGPU / SCANcontroller.
//
// Scope of this pass: the 4 inverse projections, the VisualHiRes/VisualLoRes coverage
// stencil, the base ScaledSpace colour, the normal-map soft-light shading, grayscale mode,
// and the day/night terminator. Resource-overlay maps still fall back to the CPU path.
//
// NOTE: rebuild the scan_shaders asset bundle (SCANsat -> Build All Bundles, Unity
// 2019.4.18f1) for this to be picked up at runtime; until then SCANsat uses the CPU path.
Shader "Hidden/SCANsat/VisualComposite"
{
	Properties
	{
		_ScaledColor ("Scaled Color", 2D) = "gray" {}
		_ScaledNormal ("Scaled Normal", 2D) = "bump" {}
		_CoverageFlags ("Coverage Flags", 2D) = "black" {}
		// Cosmetic sweep reveal. Defaults render the whole map (SweepY >= 1) so a fresh
		// Material is fully revealed even if the C# side never sets these (bundle/DLL skew).
		_SweepY ("Sweep Reveal", Float) = 1
		_MapBackgroundColor ("Map Background", Color) = (0,0,0,1)
		_RedlineColor ("Redline", Color) = (1,0,0,1)
	}
	SubShader
	{
		Cull Off ZWrite Off ZTest Always

		Pass
		{
			CGPROGRAM
			#pragma vertex vert_img
			#pragma fragment frag
			#include "UnityCG.cginc"

			sampler2D _ScaledColor;
			sampler2D _ScaledNormal;
			sampler2D _CoverageFlags;   // 360x180, point-sampled. R=VisualHiRes G=VisualLoRes (B/A reserved)

			// Projection / map framing (mirror SCANmap fields)
			float _MapWidth;
			float _MapHeight;
			float _MapScale;
			float _LonOffset;
			float _LatOffset;
			float _Projection;      // 0 Rectangular, 1 KavrayskiyVII, 2 Polar, 3 Orthographic
			float _CenteredLon;
			float _CenteredLat;
			float _FlipY;           // 1 to flip the vertical axis (Blit Y-orientation safety toggle)

			// Visual layer
			float _ColorMode;       // 1 colour, 0 grayscale
			float _HasNormal;       // 1 if a normal map is bound

			// Terminator
			float _Terminator;      // 1 on
			float _SunLonCenter;
			float _SunLatCenter;
			float _Gamma;

			float4 _UnscannedColor;
			float4 _ClearColor;

			// Cosmetic sweep reveal (matches the CPU modes' line-by-line render look). The GPU
			// composites the whole map at once, so the "sweep" is layered on afterwards: rows
			// ahead of the scanline are drawn as background, the frontier row as a redline.
			float _SweepY;                 // revealed fraction in texture-row space (uv.y). >=1 = done, no redline.
			float4 _MapBackgroundColor;    // unrevealed rows (SCAN settings MapBackgroundColor * transparency)
			float4 _RedlineColor;          // the advancing scanline colour (palette.Red)

			static const float SCAN_PI = 3.14159265358979;
			static const float DEG2RAD = 0.0174532925199433;
			static const float RAD2DEG = 57.2957795130823;

			// SCANmap.unprojectLongitude/unprojectLatitude prologue + normalization.
			void normalizeRaw(inout float lon, inout float lat)
			{
				if (lat > 90.0) { lat = 180.0 - lat; lon += 180.0; }
				else if (lat < -90.0) { lat = -180.0 - lat; lon += 180.0; }
				lon = fmod(lon + 3600.0 + 180.0, 360.0) - 180.0;
				lat = fmod(lat + 1800.0 + 90.0, 180.0) - 90.0;
			}

			// Pixel raw coords -> geographic lon/lat (degrees). Returns false for pixels that
			// fall outside the projected disc (drawn as _ClearColor), matching the CPU guard
			// `IsNaN || lat<-90 || lat>90 || lon<-180 || lon>180`.
			bool unproject(float lonRaw, float latRaw, out float lon, out float lat)
			{
				normalizeRaw(lonRaw, latRaw);
				lon = lonRaw;
				lat = latRaw;

				if (_Projection < 0.5)               // Rectangular
				{
					// identity
				}
				else if (_Projection < 1.5)          // KavrayskiyVII (lat unchanged)
				{
					float lonr = DEG2RAD * lonRaw;
					float latr = DEG2RAD * latRaw;
					lon = RAD2DEG * (lonr / sqrt(SCAN_PI * SCAN_PI / 3.0 - latr * latr) * 2.0 * SCAN_PI / 3.0);
					lat = latRaw;
				}
				else if (_Projection < 2.5)          // Polar
				{
					float lonr = DEG2RAD * lonRaw;
					float latr = DEG2RAD * latRaw;
					float lat0 = SCAN_PI / 2.0;
					if (lonr < 0.0) { lonr += SCAN_PI / 2.0; lat0 = -SCAN_PI / 2.0; }
					else { lonr -= SCAN_PI / 2.0; }
					lonr /= 1.3;
					latr /= 1.3;
					float p = sqrt(lonr * lonr + latr * latr);
					float c = asin(p);
					float gl = atan2(lonr * sin(c), p * cos(lat0) * cos(c) - latr * sin(lat0) * sin(c));
					gl = fmod(RAD2DEG * gl + 180.0, 360.0) - 180.0;
					if (gl <= -180.0) gl = -180.0;
					lon = gl;
					lat = RAD2DEG * asin(cos(c) * sin(lat0) + (latr * sin(c) * cos(lat0)) / p);
				}
				else                                  // Orthographic
				{
					float lonr = DEG2RAD * lonRaw;
					float latr = DEG2RAD * latRaw;
					float centerLon = DEG2RAD * _CenteredLon;
					float centerLat = DEG2RAD * _CenteredLat;
					float p2 = sqrt(lonr * lonr + latr * latr);
					float c2 = asin(p2 / 1.5);
					if (cos(c2) < 0.0) return false;   // back hemisphere
					float gl = centerLon + atan2(lonr * sin(c2), p2 * cos(c2) * cos(centerLat) - latr * sin(c2) * sin(centerLat));
					gl = fmod(RAD2DEG * gl + 180.0, 360.0) - 180.0;
					if (gl <= -180.0) gl += 360.0;
					lon = gl;
					lat = RAD2DEG * asin(cos(c2) * sin(centerLat) + (latr * sin(c2) * cos(centerLat)) / p2);
				}

				if (isnan(lon) || isnan(lat)) return false;
				if (lat < -90.0 || lat > 90.0 || lon < -180.0 || lon > 180.0) return false;
				return true;
			}

			// SCANcolorUtil.ConvertToGrayscale weights.
			float3 grayscale(float3 c)
			{
				float l = saturate(c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722);
				return float3(l, l, l);
			}

			float3 rgb2hsl(float3 c)
			{
				float mn = min(min(c.r, c.g), c.b);
				float mx = max(max(c.r, c.g), c.b);
				float l = (mn + mx) * 0.5;
				float h = 0.0, s = 0.0;
				if (mn != mx)
				{
					float d = mx - mn;
					s = l < 0.5 ? d / (mx + mn) : d / (2.0 - mx - mn);
					if (mx == c.r)      h = (c.g - c.b) / d + (c.g < c.b ? 6.0 : 0.0);
					else if (mx == c.g) h = (c.b - c.r) / d + 2.0;
					else                h = (c.r - c.g) / d + 4.0;
					h /= 6.0;
				}
				return float3(h, s, l);
			}

			float hue2rgb(float p, float q, float t)
			{
				if (t < 0.0) t += 1.0;
				if (t > 1.0) t -= 1.0;
				if (t < 1.0 / 6.0) return p + (q - p) * 6.0 * t;
				if (t < 1.0 / 2.0) return q;
				if (t < 2.0 / 3.0) return p + (q - p) * (2.0 / 3.0 - t) * 6.0;
				return p;
			}

			float3 hsl2rgb(float3 hsl)
			{
				if (hsl.y == 0.0) return float3(hsl.z, hsl.z, hsl.z);
				float q = hsl.z < 0.5 ? hsl.z * (1.0 + hsl.y) : hsl.z + hsl.y - hsl.z * hsl.y;
				float p = 2.0 * hsl.z - q;
				return float3(hue2rgb(p, q, hsl.x + 1.0 / 3.0), hue2rgb(p, q, hsl.x), hue2rgb(p, q, hsl.x - 1.0 / 3.0));
			}

			// SCANmap.cs ~1205-1237: modulate lightness by the normal map's blue channel.
			float3 normalSoftLight(float3 rgb, float lumOver)
			{
				float3 hsl = rgb2hsl(rgb);
				float lum = hsl.z;
				float opacity = 0.8;
				if (lum > 0.5)
					lum = opacity * (1.0 - (1.0 - (2.0 * (lumOver - 0.5))) * (1.0 - lum)) + (1.0 - opacity) * lum;
				else
					lum = opacity * (2.0 * lumOver * lum) + (1.0 - opacity) * lum;
				return hsl2rgb(float3(hsl.x, hsl.y, lum));
			}

			fixed4 frag(v2f_img i) : SV_Target
			{
				float vy = _FlipY > 0.5 ? 1.0 - i.uv.y : i.uv.y;

				// Pixel -> raw coord (SCANmap.cs:1023-1024), then unproject.
				float lonRaw = (i.uv.x * _MapWidth / _MapScale) - 180.0 + _LonOffset;
				float latRaw = (vy * _MapHeight / _MapScale) - 90.0 + _LatOffset;

				float lon, lat;
				if (!unproject(lonRaw, latRaw, lon, lat))
					return _ClearColor;

				// Coverage stencil lookup (SCANUtil.icLON/icLAT -> Coverage[ilon,ilat]).
				float ilon = fmod(floor(lon + 540.0), 360.0);
				float ilat = fmod(floor(lat + 270.0), 180.0);
				float4 flags = tex2D(_CoverageFlags, float2((ilon + 0.5) / 360.0, (ilat + 0.5) / 180.0));
				bool visHi = flags.r > 0.5;
				bool visLo = flags.g > 0.5;

				// Base ScaledSpace UV (SCANmap.cs:1183-1199).
				float fLat = saturate((lat + 90.0) / 180.0);
				float fLon = (lon + 270.0) / 360.0;
				if (fLon < 0.0) fLon += 1.0;
				if (fLon > 1.0) fLon -= 1.0;
				fLon = saturate(1.0 - fLon);

				float4 col;
				if (visHi)
				{
					col = tex2D(_ScaledColor, float2(fLon, fLat));
					if (_ColorMode > 0.5)
					{
						if (_HasNormal > 0.5)
							col.rgb = normalSoftLight(col.rgb, tex2D(_ScaledNormal, float2(fLon, fLat)).b);
					}
					else
					{
						col.rgb = grayscale(col.rgb);
					}
					// The raw ScaledSpace colour texture carries alpha ~0 (unlike the CPU path, which
					// reads a copy produced by an opaque material Blit). Force opaque, else the map is
					// drawn nearly transparent - a faint ghost of the planet.
					col.a = 1.0;
				}
				else if (visLo)
				{
					// Coarse 512x256 nearest sample (SCANmap.cs:1260-1302).
					float2 q = float2(floor(fLon * 512.0) / 512.0, floor(fLat * 256.0) / 256.0);
					col = tex2D(_ScaledColor, q);
					if (_ColorMode <= 0.5)
						col.rgb = grayscale(col.rgb);
					col.a = 1.0;
				}
				else
				{
					col = _UnscannedColor;
				}

				// Terminator day/night darkening (SCANmap.cs:1342-1360).
				if (_Terminator > 0.5)
				{
					float crossingLat = atan(_Gamma * sin(DEG2RAD * lon - DEG2RAD * _SunLonCenter)) * RAD2DEG;
					bool night = _SunLatCenter >= 0.0 ? (lat < crossingLat) : (lat > crossingLat);
					if (night)
						col.rgb = lerp(col.rgb, float3(0.0, 0.0, 0.0), 0.5);
				}

				// Cosmetic top-of-the-render "sweep": reveal rows in the same order the CPU path
				// fills them (row 0..mapstep, i.e. increasing uv.y), with a ~2px red scanline at the
				// frontier. Because the RT and the CPU Texture2D share one RawImage/orientation,
				// matching the CPU's row order matches its on-screen sweep direction by construction
				// (invert the uv.y test here if in-game shows it reversed - same class of fix as _FlipY).
				if (_SweepY < 1.0)
				{
					float band = 2.0 / _MapHeight;        // scanline ~2 texture rows thick
					if (i.uv.y > _SweepY)
						col = _MapBackgroundColor;        // ahead of the line: not yet revealed
					else if (i.uv.y > _SweepY - band)
						col = _RedlineColor;              // the advancing scanline
					// else: already swept - keep the composited colour
				}

				return col;
			}
			ENDCG
		}
	}
	Fallback Off
}
