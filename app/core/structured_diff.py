"""
Structured Data Comparison Engine (JSON, YAML, XML)
Hierarchical tree diffing that normalizes keys, ignores reordering,
and evaluates structural differences independently of formatting or indentation.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict
import json
import xml.etree.ElementTree as ET

try:
    import defusedxml.ElementTree as safe_ET
except ImportError:
    safe_ET = None

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class StructuredNode:
    name: str
    path: str
    node_type: str  # 'object', 'array', 'value', 'element'
    left_val: Any = None
    right_val: Any = None
    status: str = "equal"  # 'equal', 'added', 'deleted', 'modified'
    children: List["StructuredNode"] = field(default_factory=list)


@dataclass
class StructuredDiffResult:
    root_node: StructuredNode
    total_nodes: int
    added_count: int
    deleted_count: int
    modified_count: int
    equal_count: int
    format_type: str


class StructuredDiffEngine:
    """Core hierarchical differencing for structured data formats."""

    @staticmethod
    def parse_content(text: str, format_type: str = "auto") -> Tuple[Any, str]:
        """Parses text into a generic Python structure or XML element."""
        fmt = format_type.lower()
        if fmt == "auto":
            # Auto-detect
            trimmed = text.strip()
            if trimmed.startswith("<") and trimmed.endswith(">"):
                fmt = "xml"
            elif (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
                fmt = "json"
            else:
                fmt = "yaml" if yaml else "json"

        if fmt == "json":
            return json.loads(text), "json"
        elif fmt == "yaml":
            if yaml is None:
                raise ImportError("PyYAML is not installed.")
            return yaml.safe_load(text), "yaml"
        elif fmt == "xml":
            if safe_ET is not None:
                return safe_ET.fromstring(text), "xml"
            return ET.fromstring(text), "xml"  # nosec B314
        else:
            raise ValueError(f"Unsupported structured format: {format_type}")

    @classmethod
    def compare(
        cls,
        left_text: str,
        right_text: str,
        format_type: str = "auto",
        ignore_key_order: bool = True,
        unordered_arrays: bool = False,
        query: Optional[str] = None
    ) -> StructuredDiffResult:
        """Performs hierarchical tree diffing across Left and Right structured documents with optional query filtering and unordered array matching."""
        try:
            left_obj, detected_fmt = cls.parse_content(left_text, format_type)
            right_obj, _ = cls.parse_content(right_text, detected_fmt)
        except Exception as e:
            # Fallback for parse errors
            root = StructuredNode(
                name="Parse Error",
                path="root",
                node_type="error",
                left_val=str(e),
                right_val=str(e),
                status="modified"
            )
            return StructuredDiffResult(root, 1, 0, 0, 1, 0, "error")

        # Optional JSONPath or XPath query filtering
        if query and query.strip():
            q = query.strip()
            if detected_fmt == "xml":
                try:
                    l_matches = left_obj.findall(q) if left_obj is not None else []
                    r_matches = right_obj.findall(q) if right_obj is not None else []
                    l_virtual = ET.Element("query_results")
                    for elem in l_matches:
                        l_virtual.append(elem)
                    r_virtual = ET.Element("query_results")
                    for elem in r_matches:
                        r_virtual.append(elem)
                    left_obj, right_obj = l_virtual, r_virtual
                except Exception as qe:
                    root = StructuredNode(
                        name=f"XPath Query Error ({q})",
                        path="query",
                        node_type="error",
                        left_val=str(qe),
                        right_val=str(qe),
                        status="modified"
                    )
                    return StructuredDiffResult(root, 1, 0, 0, 1, 0, detected_fmt)
            else:
                try:
                    import jsonpath_ng
                    expr = jsonpath_ng.parse(q)
                    l_matches = [m.value for m in expr.find(left_obj)] if left_obj is not None else []
                    r_matches = [m.value for m in expr.find(right_obj)] if right_obj is not None else []
                    left_obj = l_matches
                    right_obj = r_matches
                except Exception as qe:
                    root = StructuredNode(
                        name=f"JSONPath Query Error ({q})",
                        path="query",
                        node_type="error",
                        left_val=str(qe),
                        right_val=str(qe),
                        status="modified"
                    )
                    return StructuredDiffResult(root, 1, 0, 0, 1, 0, detected_fmt)

        if detected_fmt == "xml":
            root = cls._compare_xml_nodes(left_obj, right_obj, path="root")
        else:
            root = cls._compare_json_nodes(
                left_obj, right_obj, path="root", name="root",
                ignore_key_order=ignore_key_order,
                unordered_arrays=unordered_arrays
            )

        # Aggregate metrics
        counts = {"added": 0, "deleted": 0, "modified": 0, "equal": 0}
        total = cls._count_nodes(root, counts)

        return StructuredDiffResult(
            root_node=root,
            total_nodes=total,
            added_count=counts["added"],
            deleted_count=counts["deleted"],
            modified_count=counts["modified"],
            equal_count=counts["equal"],
            format_type=detected_fmt
        )

    @classmethod
    def _compare_unordered_arrays(
        cls,
        l_list: list,
        r_list: list,
        path: str,
        name: str,
        ignore_key_order: bool = True
    ) -> StructuredNode:
        """Semantically compares two JSON arrays ignoring element order."""
        node = StructuredNode(name=name, path=path, node_type="array")
        node_status = "equal"

        matched_r_indices = set()
        unmatched_l = []

        # Pass 1: Exact matches
        for l_idx, l_item in enumerate(l_list):
            found_match = False
            for r_idx, r_item in enumerate(r_list):
                if r_idx in matched_r_indices:
                    continue
                if l_item == r_item:
                    child = cls._compare_json_nodes(
                        l_item, r_item, f"{path}[{l_idx}]", f"[~{l_idx}]",
                        ignore_key_order=ignore_key_order,
                        unordered_arrays=True
                    )
                    node.children.append(child)
                    matched_r_indices.add(r_idx)
                    found_match = True
                    break
            if not found_match:
                unmatched_l.append((l_idx, l_item))

        # Pass 2: Dicts with matching identifying keys ('id', 'key', 'name', 'uuid')
        id_keys = ("id", "_id", "key", "name", "uuid", "pk")
        remaining_l = []
        for l_idx, l_item in unmatched_l:
            found_match = False
            if isinstance(l_item, dict):
                for ik in id_keys:
                    if ik in l_item:
                        l_id = l_item[ik]
                        for r_idx, r_item in enumerate(r_list):
                            if r_idx in matched_r_indices or not isinstance(r_item, dict):
                                continue
                            if r_item.get(ik) == l_id:
                                child = cls._compare_json_nodes(
                                    l_item, r_item, f"{path}[{l_idx}]", f"[~{l_idx}]",
                                    ignore_key_order=ignore_key_order,
                                    unordered_arrays=True
                                )
                                node.children.append(child)
                                if child.status != "equal":
                                    node_status = "modified"
                                matched_r_indices.add(r_idx)
                                found_match = True
                                break
                        if found_match:
                            break
            if not found_match:
                remaining_l.append((l_idx, l_item))

        # Pass 3: Leftover unmatched items on Left -> Deleted
        for l_idx, l_item in remaining_l:
            child = cls._build_single_tree(l_item, f"{path}[{l_idx}]", f"[{l_idx}]", is_left=True)
            node.children.append(child)
            node_status = "modified"

        # Pass 4: Leftover unmatched items on Right -> Added
        for r_idx, r_item in enumerate(r_list):
            if r_idx not in matched_r_indices:
                child = cls._build_single_tree(r_item, f"{path}[{r_idx}]", f"[{r_idx}]", is_left=False)
                node.children.append(child)
                node_status = "modified"

        node.status = node_status
        return node

    @classmethod
    def _compare_json_nodes(
        cls,
        l_val: Any,
        r_val: Any,
        path: str,
        name: str,
        ignore_key_order: bool = True,
        unordered_arrays: bool = False
    ) -> StructuredNode:
        # Check type mismatch
        if l_val is not None and r_val is not None and type(l_val) != type(r_val):
            return StructuredNode(
                name=name,
                path=path,
                node_type="value",
                left_val=l_val,
                right_val=r_val,
                status="modified"
            )

        # 1. Dictionaries / Objects
        if isinstance(l_val, dict) or isinstance(r_val, dict):
            l_dict = l_val if isinstance(l_val, dict) else {}
            r_dict = r_val if isinstance(r_val, dict) else {}

            all_keys = set(l_dict.keys()) | set(r_dict.keys())
            sorted_keys = sorted(all_keys) if ignore_key_order else list(all_keys)

            node = StructuredNode(name=name, path=path, node_type="object")
            node_status = "equal"

            for k in sorted_keys:
                sub_path = f"{path}.{k}"
                if k in l_dict and k not in r_dict:
                    child = cls._build_single_tree(l_dict[k], sub_path, str(k), is_left=True)
                    node.children.append(child)
                    node_status = "modified"
                elif k in r_dict and k not in l_dict:
                    child = cls._build_single_tree(r_dict[k], sub_path, str(k), is_left=False)
                    node.children.append(child)
                    node_status = "modified"
                else:
                    child = cls._compare_json_nodes(
                        l_dict[k], r_dict[k], sub_path, str(k),
                        ignore_key_order=ignore_key_order,
                        unordered_arrays=unordered_arrays
                    )
                    node.children.append(child)
                    if child.status != "equal":
                        node_status = "modified"

            node.status = node_status
            return node

        # 2. Lists / Arrays
        if isinstance(l_val, list) or isinstance(r_val, list):
            l_list = l_val if isinstance(l_val, list) else []
            r_list = r_val if isinstance(r_val, list) else []

            if unordered_arrays:
                return cls._compare_unordered_arrays(
                    l_list, r_list, path, name, ignore_key_order=ignore_key_order
                )

            max_len = max(len(l_list), len(r_list))
            node = StructuredNode(name=name, path=path, node_type="array")
            node_status = "equal"

            for idx in range(max_len):
                sub_path = f"{path}[{idx}]"
                sub_name = f"[{idx}]"
                if idx < len(l_list) and idx >= len(r_list):
                    child = cls._build_single_tree(l_list[idx], sub_path, sub_name, is_left=True)
                    node.children.append(child)
                    node_status = "modified"
                elif idx < len(r_list) and idx >= len(l_list):
                    child = cls._build_single_tree(r_list[idx], sub_path, sub_name, is_left=False)
                    node.children.append(child)
                    node_status = "modified"
                else:
                    child = cls._compare_json_nodes(
                        l_list[idx], r_list[idx], sub_path, sub_name,
                        ignore_key_order=ignore_key_order,
                        unordered_arrays=unordered_arrays
                    )
                    node.children.append(child)
                    if child.status != "equal":
                        node_status = "modified"

            node.status = node_status
            return node

        # 3. Scalar Values
        if l_val == r_val:
            return StructuredNode(
                name=name, path=path, node_type="value", left_val=l_val, right_val=r_val, status="equal"
            )
        else:
            return StructuredNode(
                name=name, path=path, node_type="value", left_val=l_val, right_val=r_val, status="modified"
            )

    @classmethod
    def _build_single_tree(cls, val: Any, path: str, name: str, is_left: bool) -> StructuredNode:
        status = "deleted" if is_left else "added"
        if isinstance(val, dict):
            node = StructuredNode(name=name, path=path, node_type="object", status=status)
            for k, v in sorted(val.items()):
                node.children.append(cls._build_single_tree(v, f"{path}.{k}", str(k), is_left))
            return node
        elif isinstance(val, list):
            node = StructuredNode(name=name, path=path, node_type="array", status=status)
            for idx, item in enumerate(val):
                node.children.append(cls._build_single_tree(item, f"{path}[{idx}]", f"[{idx}]", is_left))
            return node
        else:
            return StructuredNode(
                name=name,
                path=path,
                node_type="value",
                left_val=val if is_left else None,
                right_val=val if not is_left else None,
                status=status
            )

    @classmethod
    def _compare_xml_nodes(cls, l_elem: ET.Element, r_elem: ET.Element, path: str) -> StructuredNode:
        tag = l_elem.tag if l_elem is not None else (r_elem.tag if r_elem is not None else "elem")
        node = StructuredNode(name=tag, path=path, node_type="element")

        l_text = (l_elem.text or "").strip() if l_elem is not None else None
        r_text = (r_elem.text or "").strip() if r_elem is not None else None

        node.left_val = l_text
        node.right_val = r_text

        # Compare attributes
        l_attrib = l_elem.attrib if l_elem is not None else {}
        r_attrib = r_elem.attrib if r_elem is not None else {}
        all_attrs = set(l_attrib.keys()) | set(r_attrib.keys())

        for attr in sorted(all_attrs):
            attr_path = f"{path}@{attr}"
            if attr in l_attrib and attr not in r_attrib:
                node.children.append(StructuredNode(f"@{attr}", attr_path, "attribute", left_val=l_attrib[attr], status="deleted"))
            elif attr in r_attrib and attr not in l_attrib:
                node.children.append(StructuredNode(f"@{attr}", attr_path, "attribute", right_val=r_attrib[attr], status="added"))
            else:
                st = "equal" if l_attrib[attr] == r_attrib[attr] else "modified"
                node.children.append(StructuredNode(f"@{attr}", attr_path, "attribute", left_val=l_attrib[attr], right_val=r_attrib[attr], status=st))

        # Children tags
        l_kids = list(l_elem) if l_elem is not None else []
        r_kids = list(r_elem) if r_elem is not None else []
        max_kids = max(len(l_kids), len(r_kids))

        for i in range(max_kids):
            k_path = f"{path}/{i}"
            if i < len(l_kids) and i < len(r_kids):
                node.children.append(cls._compare_xml_nodes(l_kids[i], r_kids[i], k_path))
            elif i < len(l_kids):
                node.children.append(cls._compare_xml_nodes(l_kids[i], None, k_path))
            else:
                node.children.append(cls._compare_xml_nodes(None, r_kids[i], k_path))

        # Status check
        if l_elem is None:
            node.status = "added"
        elif r_elem is None:
            node.status = "deleted"
        elif l_text != r_text or any(c.status != "equal" for c in node.children):
            node.status = "modified"
        else:
            node.status = "equal"

        return node

    @classmethod
    def _count_nodes(cls, node: StructuredNode, counts: Dict[str, int]) -> int:
        counts[node.status] = counts.get(node.status, 0) + 1
        total = 1
        for child in node.children:
            total += cls._count_nodes(child, counts)
        return total
