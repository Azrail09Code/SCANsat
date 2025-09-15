#region license
/* 
 * [Scientific Committee on Advanced Navigation]
 * 			S.C.A.N. Satellite
 *
 * SCANreflection - assigns reflection methods at startup
 * 
 * Copyright (c)2014 David Grandy <david.grandy@gmail.com>;
 * Copyright (c)2014 technogeeky <technogeeky@gmail.com>;
 * Copyright (c)2014 (Your Name Here) <your email here>; see LICENSE.txt for licensing details.
 */
#endregion

using System;
using System.Reflection;
using FinePrint;
using FinePrint.Contracts.Parameters;
using FinePrint.Utilities;
using UnityEngine;

namespace SCANsat.SCAN_Reflection
{
	static class SCANkopernicus
	{
		public const string KOPERNICUSONDEMANDTYPE = "ScaledSpaceOnDemand";
		private const string KOPERNICUSONDEMANDLOAD = "LoadTextures";
		private const string KOPERNICUSONDEMANDUNLOAD = "UnloadTextures";

		internal static void LoadOnDemand(MonoBehaviour scaledSpaceOnDemand)
		{
			scaledSpaceOnDemand.GetType().InvokeMember(KOPERNICUSONDEMANDLOAD
				, BindingFlags.Instance | BindingFlags.Public | BindingFlags.IgnoreReturn | BindingFlags.InvokeMethod, null, scaledSpaceOnDemand, null);
		}

		internal static void UnloadOnDemand(MonoBehaviour scaledSpaceOnDemand)
		{
			scaledSpaceOnDemand.GetType().InvokeMember(KOPERNICUSONDEMANDUNLOAD
				, BindingFlags.Instance | BindingFlags.Public | BindingFlags.IgnoreReturn | BindingFlags.InvokeMethod, null, scaledSpaceOnDemand, null);
		}
	}
}
