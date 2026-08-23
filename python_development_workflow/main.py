"""
RenderDoc script to find the top 100 textures and buffers by memory usage.
This script can be run from the RenderDoc Python Shell or as a standalone script.
"""

import renderdoc as rd

top_n = 100

def analyze_memory_usage(controller):
    """
    Analyze all textures and buffers in the capture and display top 100 by memory usage.
    Args:
        controller: RenderDoc ReplayController instance
    """
    print("=" * 80)
    print("RenderDoc Memory Usage Analysis")
    print("=" * 80)

    # Get all resources to build a name lookup dictionary
    resources = controller.GetResources()
    resource_names = {}
    for res in resources:
        resource_names[res.resourceId] = res.name if res.name else f"Resource_{res.resourceId}"

    # Get all textures and buffers from the capture
    textures = controller.GetTextures()
    buffers = controller.GetBuffers()

    texture_list = []
    buffer_list = []

    # Process all textures
    for tex_desc in textures:
        res_id = tex_desc.resourceId
        name = resource_names.get(res_id, f"Texture_{res_id}")

        texture_list.append({
            'id': res_id,
            'name': name,
            'size': tex_desc.byteSize,
            'width': tex_desc.width,
            'height': tex_desc.height,
            'depth': tex_desc.depth,
            'mips': tex_desc.mips,
            'arraysize': tex_desc.arraysize,
            'format': str(tex_desc.format.Name())
        })

    # Process all buffers
    for buf_desc in buffers:
        res_id = buf_desc.resourceId
        name = resource_names.get(res_id, f"Buffer_{res_id}")

        buffer_list.append({
            'id': res_id,
            'name': name,
            'size': buf_desc.length,
            'creation_flags': str(buf_desc.creationFlags)
        })

    # Sort by size (descending)
    texture_list.sort(key=lambda x: x['size'], reverse=True)
    buffer_list.sort(key=lambda x: x['size'], reverse=True)

    # Combine and get top 100
    combined_list = []

    for tex in texture_list:
        combined_list.append({
            'type': 'Texture',
            'name': tex['name'],
            'size': tex['size'],
            'details': f"{tex['width']}x{tex['height']}x{tex['depth']}, {tex['mips']} mips, {tex['arraysize']} array, {tex['format']}"
        })

    for buf in buffer_list:
        combined_list.append({
            'type': 'Buffer',
            'name': buf['name'],
            'size': buf['size'],
            'details': buf['creation_flags']
        })

    # Sort combined list by size
    combined_list.sort(key=lambda x: x['size'], reverse=True)

    # Get top 100
    top_100 = combined_list[:top_n]

    # Display summary statistics
    total_texture_memory = sum(tex['size'] for tex in texture_list)
    total_buffer_memory = sum(buf['size'] for buf in buffer_list)
    total_memory = total_texture_memory + total_buffer_memory

    print(f"\nSummary Statistics:")
    print(f"  Total Textures: {len(texture_list)}")
    print(f"  Total Buffers: {len(buffer_list)}")
    print(f"  Total Texture Memory: {format_bytes(total_texture_memory)}")
    print(f"  Total Buffer Memory: {format_bytes(total_buffer_memory)}")
    print(f"  Total Memory: {format_bytes(total_memory)}")
    print()

    # Calculate dynamic name column width (max 128)
    max_name_width = min(max((len(item['name']) for item in top_100), default=30), 128)
    # Ensure minimum width for readability
    name_col_width = max(max_name_width, 20)

    # Calculate total table width
    table_width = 6 + 10 + 15 + name_col_width + 50 + 5  # columns + spacing

    # Display top 100
    print(f"\nTop {len(top_100)} Resources by Memory Usage:")
    print("=" * table_width)
    print(f"{'Rank':<6} {'Type':<10} {'Size':<15} {'Name':<{name_col_width}} {'Details'}")
    print("-" * table_width)

    for i, item in enumerate(top_100, 1):
        size_str = format_bytes(item['size'])
        name_truncated = item['name'][:name_col_width]
        details_truncated = item['details'][:50] if len(item['details']) <= 50 else item['details'][:47] + "..."

        print(f"{i:<6} {item['type']:<10} {size_str:<15} {name_truncated:<{name_col_width}} {details_truncated}")

    print("=" * table_width)

    # Display top 10 textures specifically
    print("\nTop 10 Textures:")
    print("-" * 80)
    for i, tex in enumerate(texture_list[:10], 1):
        print(f"{i}. {tex['name']} - {format_bytes(tex['size'])}")
        print(f"   Dimensions: {tex['width']}x{tex['height']}x{tex['depth']}, Mips: {tex['mips']}, Array: {tex['arraysize']}")
        print(f"   Format: {tex['format']}")
        print()

    # Display top 10 buffers specifically
    print("\nTop 10 Buffers:")
    print("-" * 80)
    for i, buf in enumerate(buffer_list[:10], 1):
        print(f"{i}. {buf['name']} - {format_bytes(buf['size'])}")
        print(f"   Flags: {buf['creation_flags']}")
        print()


def format_bytes(bytes_value):
    """
    Format byte size into human-readable string.
    Args:
        bytes_value: Size in bytes
    Returns:
        Formatted string with appropriate unit (B, KB, MB, GB)
    """
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.2f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"


# Entry point for running within RenderDoc UI
if 'pyrenderdoc' in globals():
    # Running in RenderDoc UI - use the global pyrenderdoc object
    pyrenderdoc.Replay().BlockInvoke(analyze_memory_usage)
else:
    # Running as standalone script - need to load capture manually
    print("This script should be run from within RenderDoc.")
    print("Open a capture in RenderDoc and run this script from Tools -> Python Shell")
    print("\nAlternatively, you can modify this script to load a capture file:")
    print("  cap = rd.OpenCaptureFile()")
    print("  status = cap.OpenFile('path/to/capture.rdc', '', None)")
    print("  if status == rd.ReplayStatus.Succeeded:")
    print("      cap.InitResolver(False, None)")
    print("      controller = cap.OpenCapture(rd.CaptureOptions(), None)")
    print("      analyze_memory_usage(controller)")
    print("      controller.Shutdown()")
    print("  cap.Shutdown()")