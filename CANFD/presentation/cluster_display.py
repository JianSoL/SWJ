"""User-facing cluster labels.

Protocol services keep zero-based internal indexes. The deployed BCU address
scheme is user-facing and one-based: A0 is cluster 1, A1 is cluster 2, and so
on. Keeping that conversion here prevents control messages from showing a
misleading cluster number while preserving the protocol index unchanged.
"""


def cluster_display_number(cluster_index, address):
    normalized_address = str(address or "").strip().upper()
    if len(normalized_address) == 2 and normalized_address.startswith("A"):
        try:
            return int(normalized_address[1], 16) + 1
        except ValueError:
            pass
    return int(cluster_index)


def format_cluster_short_name(cluster_index, address):
    if str(address or "").strip().upper() == "00":
        return "未编制簇"
    return f"簇{cluster_display_number(cluster_index, address)}"


def format_cluster_name(cluster_index, address):
    if str(address or "").strip().upper() == "00":
        return "未编制簇 (00)"
    return (
        f"{format_cluster_short_name(cluster_index, address)} "
        f"({str(address or '--').upper()})"
    )


def format_cluster_context(cluster_index, address):
    if str(address or "").strip().upper() == "00":
        return "当前簇: 未编制簇 / 地址 00"
    number = cluster_display_number(cluster_index, address)
    return f"当前簇: 簇{number} / 地址 {str(address or '--').upper()}"
