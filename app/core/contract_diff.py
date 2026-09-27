"""
Contract & Semantic API Schema Difference Engine
Specialized semantic differ for API contracts:
1. OpenAPI / Swagger 2.0 & 3.x (JSON / YAML)
2. GraphQL Schema Definition Language (.graphql / .gql)
3. Protocol Buffers v2 & v3 (.proto)

Classifies changes into:
- 🔴 BREAKING: Removed endpoints/methods, newly required parameters, field type modifications, tag collisions
- 🟡 WARNING: Deprecated APIs, removed optional parameters
- 🟢 ADDITIVE: New endpoints, new optional fields, new RPCs
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
import re
import json

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class ContractChange:
    """Represents a specific semantic change in an API contract."""
    category: str        # 'BREAKING', 'WARNING', 'ADDITIVE'
    contract_type: str   # 'OpenAPI', 'GraphQL', 'Protobuf'
    entity_path: str     # e.g., 'POST /api/v1/users -> email' or 'User.email'
    change_type: str     # 'REMOVED_ENDPOINT', 'TYPE_MODIFIED', 'TAG_CHANGED', etc.
    description: str     # Human-readable explanation of impact
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class ContractDiffReport:
    """Complete summary and breakdown of API contract differences."""
    contract_type: str
    breaking_count: int
    warning_count: int
    additive_count: int
    changes: List[ContractChange] = field(default_factory=list)

    @property
    def has_breaking_changes(self) -> bool:
        return self.breaking_count > 0


class ContractDiffEngine:
    """Core engine for detecting and analyzing API contract differences."""

    @staticmethod
    def detect_format(content: str, filename: str = "") -> Optional[str]:
        """Detects whether content or filename represents an API contract."""
        lower_fn = filename.lower()
        if lower_fn.endswith((".graphql", ".gql")):
            return "GraphQL"
        if lower_fn.endswith(".proto"):
            return "Protobuf"
        if lower_fn.endswith((".swagger.json", ".swagger.yaml", ".swagger.yml", ".openapi.json", ".openapi.yaml", ".openapi.yml")):
            return "OpenAPI"

        trimmed = content.strip()
        if not trimmed:
            return None

        # Protobuf check
        if re.search(r'syntax\s*=\s*["\']proto[23]["\']', trimmed) or (re.search(r'\bmessage\s+\w+\s*\{', trimmed) and re.search(r'\b(service|rpc|package)\b', trimmed)):
            return "Protobuf"

        # GraphQL check
        if re.search(r'\b(type|input|interface|schema)\s+(Query|Mutation|Subscription|[A-Z]\w+)\s*\{', trimmed):
            return "GraphQL"

        # OpenAPI / Swagger check (JSON or YAML)
        if "openapi:" in trimmed or '"openapi"' in trimmed or "swagger:" in trimmed or '"swagger"' in trimmed:
            return "OpenAPI"
        if ("paths:" in trimmed or '"paths"' in trimmed) and ("info:" in trimmed or '"info"' in trimmed):
            return "OpenAPI"

        return None

    @classmethod
    def diff_contracts(
        cls,
        text_left: str,
        text_right: str,
        name_left: str = "",
        name_right: str = ""
    ) -> ContractDiffReport:
        """Analyzes differences between two contract documents."""
        fmt_left = cls.detect_format(text_left, name_left)
        fmt_right = cls.detect_format(text_right, name_right)
        fmt = fmt_right or fmt_left

        if not fmt:
            return ContractDiffReport(contract_type="Unknown", breaking_count=0, warning_count=0, additive_count=0)

        changes: List[ContractChange] = []
        if fmt == "OpenAPI":
            changes = cls._diff_openapi(text_left, text_right)
        elif fmt == "GraphQL":
            changes = cls._diff_graphql(text_left, text_right)
        elif fmt == "Protobuf":
            changes = cls._diff_protobuf(text_left, text_right)

        breaking = sum(1 for c in changes if c.category == "BREAKING")
        warning = sum(1 for c in changes if c.category == "WARNING")
        additive = sum(1 for c in changes if c.category == "ADDITIVE")

        return ContractDiffReport(
            contract_type=fmt,
            breaking_count=breaking,
            warning_count=warning,
            additive_count=additive,
            changes=changes
        )

    # -------------------------------------------------------------------------
    # 1. OpenAPI / Swagger Diffing
    # -------------------------------------------------------------------------
    @classmethod
    def _parse_spec(cls, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if not text:
            return None
        if text.startswith("{"):
            try:
                return json.loads(text)
            except Exception:
                pass
        if HAS_YAML:
            try:
                return yaml.safe_load(text)
            except Exception:
                pass
        try:
            return json.loads(text)
        except Exception:
            return None

    @classmethod
    def _diff_openapi(cls, text_left: str, text_right: str) -> List[ContractChange]:
        changes: List[ContractChange] = []
        spec1 = cls._parse_spec(text_left) or {}
        spec2 = cls._parse_spec(text_right) or {}

        paths1: Dict[str, Any] = spec1.get("paths", {}) or {}
        paths2: Dict[str, Any] = spec2.get("paths", {}) or {}

        all_paths = sorted(set(paths1.keys()) | set(paths2.keys()))
        http_methods = {"get", "post", "put", "delete", "patch", "options", "head"}

        for path in all_paths:
            if path not in paths2:
                changes.append(ContractChange(
                    category="BREAKING",
                    contract_type="OpenAPI",
                    entity_path=path,
                    change_type="ENDPOINT_REMOVED",
                    description=f"Entire path '{path}' was removed from the API contract.",
                    old_value=path,
                    new_value=None
                ))
                continue
            if path not in paths1:
                changes.append(ContractChange(
                    category="ADDITIVE",
                    contract_type="OpenAPI",
                    entity_path=path,
                    change_type="ENDPOINT_ADDED",
                    description=f"New path '{path}' was added to the API.",
                    old_value=None,
                    new_value=path
                ))
                continue

            item1 = paths1[path] or {}
            item2 = paths2[path] or {}

            for m in http_methods:
                in1 = m in item1
                in2 = m in item2
                m_upper = m.upper()
                ep_label = f"{m_upper} {path}"

                if in1 and not in2:
                    changes.append(ContractChange(
                        category="BREAKING",
                        contract_type="OpenAPI",
                        entity_path=ep_label,
                        change_type="METHOD_REMOVED",
                        description=f"HTTP method '{m_upper}' removed from '{path}'. Existing clients calling this method will receive 404/405.",
                        old_value=m_upper,
                        new_value=None
                    ))
                elif not in1 and in2:
                    changes.append(ContractChange(
                        category="ADDITIVE",
                        contract_type="OpenAPI",
                        entity_path=ep_label,
                        change_type="METHOD_ADDED",
                        description=f"New HTTP method '{m_upper}' supported on '{path}'.",
                        old_value=None,
                        new_value=m_upper
                    ))
                elif in1 and in2:
                    op1 = item1[m] or {}
                    op2 = item2[m] or {}

                    # Deprecation check
                    if not op1.get("deprecated") and op2.get("deprecated"):
                        changes.append(ContractChange(
                            category="WARNING",
                            contract_type="OpenAPI",
                            entity_path=ep_label,
                            change_type="OPERATION_DEPRECATED",
                            description=f"Operation '{ep_label}' is now marked deprecated.",
                            old_value="active",
                            new_value="deprecated"
                        ))

                    # Parameters comparison
                    params1 = {p.get("name"): p for p in op1.get("parameters", []) if isinstance(p, dict) and "name" in p}
                    params2 = {p.get("name"): p for p in op2.get("parameters", []) if isinstance(p, dict) and "name" in p}

                    for pname, pobj in params2.items():
                        if pname not in params1:
                            if pobj.get("required"):
                                changes.append(ContractChange(
                                    category="BREAKING",
                                    contract_type="OpenAPI",
                                    entity_path=f"{ep_label} -> ?{pname}",
                                    change_type="NEW_REQUIRED_PARAM",
                                    description=f"New required parameter '{pname}' added. Existing client requests omitting this parameter will fail with 400 Bad Request.",
                                    old_value=None,
                                    new_value=f"required ({pobj.get('in', 'query')})"
                                ))
                            else:
                                changes.append(ContractChange(
                                    category="ADDITIVE",
                                    contract_type="OpenAPI",
                                    entity_path=f"{ep_label} -> ?{pname}",
                                    change_type="NEW_OPTIONAL_PARAM",
                                    description=f"New optional parameter '{pname}' added ({pobj.get('in', 'query')}).",
                                    old_value=None,
                                    new_value=pname
                                ))
                        else:
                            old_p = params1[pname]
                            if not old_p.get("required") and pobj.get("required"):
                                changes.append(ContractChange(
                                    category="BREAKING",
                                    contract_type="OpenAPI",
                                    entity_path=f"{ep_label} -> ?{pname}",
                                    change_type="PARAM_NOW_REQUIRED",
                                    description=f"Parameter '{pname}' changed from optional to required.",
                                    old_value="optional",
                                    new_value="required"
                                ))
                            old_type = (old_p.get("schema") or {}).get("type") or old_p.get("type")
                            new_type = (pobj.get("schema") or {}).get("type") or pobj.get("type")
                            if old_type and new_type and old_type != new_type:
                                changes.append(ContractChange(
                                    category="BREAKING",
                                    contract_type="OpenAPI",
                                    entity_path=f"{ep_label} -> ?{pname}",
                                    change_type="PARAM_TYPE_CHANGED",
                                    description=f"Parameter '{pname}' type changed from '{old_type}' to '{new_type}'.",
                                    old_value=str(old_type),
                                    new_value=str(new_type)
                                ))

                    for pname, pobj in params1.items():
                        if pname not in params2:
                            changes.append(ContractChange(
                                category="WARNING",
                                contract_type="OpenAPI",
                                entity_path=f"{ep_label} -> ?{pname}",
                                change_type="PARAM_REMOVED",
                                description=f"Parameter '{pname}' was removed from '{ep_label}'.",
                                old_value=pname,
                                new_value=None
                            ))

                    # Response status codes
                    resp1 = op1.get("responses", {}) or {}
                    resp2 = op2.get("responses", {}) or {}
                    for code in resp1:
                        if code not in resp2:
                            changes.append(ContractChange(
                                category="BREAKING",
                                contract_type="OpenAPI",
                                entity_path=f"{ep_label} -> HTTP {code}",
                                change_type="RESPONSE_CODE_REMOVED",
                                description=f"Response status code '{code}' was removed from '{ep_label}'.",
                                old_value=str(code),
                                new_value=None
                            ))

        return changes

    # -------------------------------------------------------------------------
    # 2. GraphQL Schema Diffing
    # -------------------------------------------------------------------------
    @classmethod
    def _parse_graphql(cls, text: str) -> Dict[str, Dict[str, Any]]:
        types: Dict[str, Dict[str, Any]] = {}
        # Matches type, input, enum, interface
        blocks = re.findall(r'(type|input|enum|interface)\s+([A-Za-z0-9_]+)(?:\s+implements\s+[^{]+)?\s*\{([^}]*)\}', text)
        for kind, name, body in blocks:
            if kind == "enum":
                values = [v.strip() for v in body.strip().splitlines() if v.strip() and not v.strip().startswith("#")]
                types[name] = {"kind": "enum", "values": set(values)}
            else:
                fields: Dict[str, Dict[str, Any]] = {}
                for line in body.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r'([A-Za-z0-9_]+)(?:\(([^)]*)\))?:\s*([^\s#]+)', line)
                    if m:
                        fname, args_raw, ftype = m.groups()
                        is_non_null = ftype.endswith("!")
                        fields[fname] = {
                            "type": ftype,
                            "is_non_null": is_non_null,
                            "args": args_raw or ""
                        }
                types[name] = {"kind": kind, "fields": fields}
        return types

    @classmethod
    def _diff_graphql(cls, text_left: str, text_right: str) -> List[ContractChange]:
        changes: List[ContractChange] = []
        t1 = cls._parse_graphql(text_left)
        t2 = cls._parse_graphql(text_right)

        all_names = sorted(set(t1.keys()) | set(t2.keys()))
        for name in all_names:
            if name not in t2:
                changes.append(ContractChange(
                    category="BREAKING",
                    contract_type="GraphQL",
                    entity_path=name,
                    change_type="TYPE_REMOVED",
                    description=f"GraphQL {t1[name]['kind']} '{name}' was removed from the schema.",
                    old_value=name,
                    new_value=None
                ))
                continue
            if name not in t1:
                changes.append(ContractChange(
                    category="ADDITIVE",
                    contract_type="GraphQL",
                    entity_path=name,
                    change_type="TYPE_ADDED",
                    description=f"New GraphQL {t2[name]['kind']} '{name}' added to the schema.",
                    old_value=None,
                    new_value=name
                ))
                continue

            obj1 = t1[name]
            obj2 = t2[name]

            if obj1["kind"] == "enum" and obj2["kind"] == "enum":
                v1: Set[str] = obj1["values"]
                v2: Set[str] = obj2["values"]
                for rem in (v1 - v2):
                    changes.append(ContractChange(
                        category="BREAKING",
                        contract_type="GraphQL",
                        entity_path=f"{name}.{rem}",
                        change_type="ENUM_VALUE_REMOVED",
                        description=f"Enum value '{rem}' was removed from '{name}'. Existing queries selecting this enum will error.",
                        old_value=rem,
                        new_value=None
                    ))
                for add in (v2 - v1):
                    changes.append(ContractChange(
                        category="ADDITIVE",
                        contract_type="GraphQL",
                        entity_path=f"{name}.{add}",
                        change_type="ENUM_VALUE_ADDED",
                        description=f"New enum value '{add}' added to '{name}'.",
                        old_value=None,
                        new_value=add
                    ))
            else:
                f1: Dict[str, Dict[str, Any]] = obj1.get("fields", {})
                f2: Dict[str, Dict[str, Any]] = obj2.get("fields", {})

                for fname, finfo in f1.items():
                    if fname not in f2:
                        changes.append(ContractChange(
                            category="BREAKING",
                            contract_type="GraphQL",
                            entity_path=f"{name}.{fname}",
                            change_type="FIELD_REMOVED",
                            description=f"Field '{fname}' was removed from {obj1['kind']} '{name}'. Clients querying this field will break.",
                            old_value=finfo["type"],
                            new_value=None
                        ))

                for fname, finfo2 in f2.items():
                    if fname not in f1:
                        # If added to an input and required: breaking!
                        if obj2["kind"] == "input" and finfo2["is_non_null"]:
                            changes.append(ContractChange(
                                category="BREAKING",
                                contract_type="GraphQL",
                                entity_path=f"{name}.{fname}",
                                change_type="NEW_REQUIRED_INPUT_FIELD",
                                description=f"Newly required field '{fname}: {finfo2['type']}' added to input object '{name}'. Existing mutations omitting this field will fail validation.",
                                old_value=None,
                                new_value=finfo2["type"]
                            ))
                        else:
                            changes.append(ContractChange(
                                category="ADDITIVE",
                                contract_type="GraphQL",
                                entity_path=f"{name}.{fname}",
                                change_type="FIELD_ADDED",
                                description=f"New field '{fname}: {finfo2['type']}' added to {obj2['kind']} '{name}'.",
                                old_value=None,
                                new_value=finfo2["type"]
                            ))
                    else:
                        finfo1 = f1[fname]
                        # Check type change
                        if finfo1["type"] != finfo2["type"]:
                            # Nullable to non-null:
                            if finfo1["type"] + "!" == finfo2["type"]:
                                cat = "ADDITIVE"
                                desc = f"Field '{name}.{fname}' is now guaranteed non-null ({finfo2['type']})."
                            elif finfo1["is_non_null"] and not finfo2["is_non_null"]:
                                cat = "BREAKING"
                                desc = f"Field '{name}.{fname}' is now nullable (was non-null {finfo1['type']}). Clients assuming non-null value may throw NullPointerExceptions."
                            else:
                                cat = "BREAKING"
                                desc = f"Field '{name}.{fname}' type changed from '{finfo1['type']}' to '{finfo2['type']}'."

                            changes.append(ContractChange(
                                category=cat,
                                contract_type="GraphQL",
                                entity_path=f"{name}.{fname}",
                                change_type="FIELD_TYPE_CHANGED",
                                description=desc,
                                old_value=finfo1["type"],
                                new_value=finfo2["type"]
                            ))

        return changes

    # -------------------------------------------------------------------------
    # 3. Protocol Buffers Diffing
    # -------------------------------------------------------------------------
    @classmethod
    def _parse_proto(cls, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {"messages": {}, "services": {}}

        # Parse messages
        messages = re.findall(r'message\s+([A-Za-z0-9_]+)\s*\{([^}]*)\}', text)
        for mname, mbody in messages:
            fields: Dict[str, Dict[str, Any]] = {}
            for line in mbody.splitlines():
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                m = re.match(r'(?:(optional|repeated|required)\s+)?([A-Za-z0-9_\.]+)\s+([A-Za-z0-9_]+)\s*=\s*(\d+)\s*;', line)
                if m:
                    rule, ftype, fname, ftag = m.groups()
                    fields[fname] = {
                        "rule": rule or "optional",
                        "type": ftype,
                        "tag": int(ftag)
                    }
            data["messages"][mname] = fields

        # Parse services
        services = re.findall(r'service\s+([A-Za-z0-9_]+)\s*\{([^}]*)\}', text)
        for sname, sbody in services:
            rpcs: Dict[str, Dict[str, str]] = {}
            for line in sbody.splitlines():
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                m = re.match(r'rpc\s+([A-Za-z0-9_]+)\s*\(([^)]+)\)\s*returns\s*\(([^)]+)\)\s*;', line)
                if m:
                    rpc_name, req, resp = m.groups()
                    rpcs[rpc_name] = {
                        "req": req.strip(),
                        "resp": resp.strip()
                    }
            data["services"][sname] = rpcs

        return data

    @classmethod
    def _diff_protobuf(cls, text_left: str, text_right: str) -> List[ContractChange]:
        changes: List[ContractChange] = []
        p1 = cls._parse_proto(text_left)
        p2 = cls._parse_proto(text_right)

        # Services & RPCs
        s1 = p1["services"]
        s2 = p2["services"]
        all_services = sorted(set(s1.keys()) | set(s2.keys()))
        for sname in all_services:
            if sname not in s2:
                changes.append(ContractChange(
                    category="BREAKING",
                    contract_type="Protobuf",
                    entity_path=sname,
                    change_type="SERVICE_REMOVED",
                    description=f"gRPC service '{sname}' was removed.",
                    old_value=sname,
                    new_value=None
                ))
                continue
            if sname not in s1:
                changes.append(ContractChange(
                    category="ADDITIVE",
                    contract_type="Protobuf",
                    entity_path=sname,
                    change_type="SERVICE_ADDED",
                    description=f"New gRPC service '{sname}' added.",
                    old_value=None,
                    new_value=sname
                ))
                continue

            rpcs1 = s1[sname]
            rpcs2 = s2[sname]
            for rname in rpcs1:
                if rname not in rpcs2:
                    changes.append(ContractChange(
                        category="BREAKING",
                        contract_type="Protobuf",
                        entity_path=f"{sname}.{rname}",
                        change_type="RPC_REMOVED",
                        description=f"gRPC method '{rname}' removed from service '{sname}'.",
                        old_value=rname,
                        new_value=None
                    ))
            for rname, rinfo in rpcs2.items():
                if rname not in rpcs1:
                    changes.append(ContractChange(
                        category="ADDITIVE",
                        contract_type="Protobuf",
                        entity_path=f"{sname}.{rname}",
                        change_type="RPC_ADDED",
                        description=f"New gRPC method '{rname}({rinfo['req']}) -> {rinfo['resp']}' added.",
                        old_value=None,
                        new_value=rname
                    ))

        # Messages & Fields
        m1 = p1["messages"]
        m2 = p2["messages"]
        all_messages = sorted(set(m1.keys()) | set(m2.keys()))
        for mname in all_messages:
            if mname not in m2:
                changes.append(ContractChange(
                    category="BREAKING",
                    contract_type="Protobuf",
                    entity_path=mname,
                    change_type="MESSAGE_REMOVED",
                    description=f"Protobuf message '{mname}' was removed.",
                    old_value=mname,
                    new_value=None
                ))
                continue
            if mname not in s1 and mname not in m1:
                changes.append(ContractChange(
                    category="ADDITIVE",
                    contract_type="Protobuf",
                    entity_path=mname,
                    change_type="MESSAGE_ADDED",
                    description=f"New Protobuf message '{mname}' added.",
                    old_value=None,
                    new_value=mname
                ))
                continue

            fields1: Dict[str, Dict[str, Any]] = m1[mname]
            fields2: Dict[str, Dict[str, Any]] = m2[mname]

            # In protobuf, field tags are critical wire-format identifiers
            tag_to_field1 = {v["tag"]: (k, v) for k, v in fields1.items()}
            tag_to_field2 = {v["tag"]: (k, v) for k, v in fields2.items()}

            for fname, finfo1 in fields1.items():
                if fname not in fields2:
                    # Check if tag was reused
                    tag = finfo1["tag"]
                    if tag in tag_to_field2:
                        reused_name = tag_to_field2[tag][0]
                        changes.append(ContractChange(
                            category="BREAKING",
                            contract_type="Protobuf",
                            entity_path=f"{mname}.{fname}",
                            change_type="TAG_COLLISION",
                            description=f"Field '{fname}' (tag {tag}) was replaced by '{reused_name}' reusing the same tag {tag}! Severe wire protocol deserialization corruption.",
                            old_value=f"{fname}={tag}",
                            new_value=f"{reused_name}={tag}"
                        ))
                    else:
                        changes.append(ContractChange(
                            category="BREAKING",
                            contract_type="Protobuf",
                            entity_path=f"{mname}.{fname}",
                            change_type="FIELD_REMOVED",
                            description=f"Field '{fname}' (tag {tag}) was removed from '{mname}'. Without 'reserved {tag};', future fields risk wire tag collisions.",
                            old_value=f"{fname}={tag}",
                            new_value=None
                        ))
                else:
                    finfo2 = fields2[fname]
                    # Tag changed
                    if finfo1["tag"] != finfo2["tag"]:
                        changes.append(ContractChange(
                            category="BREAKING",
                            contract_type="Protobuf",
                            entity_path=f"{mname}.{fname}",
                            change_type="TAG_CHANGED",
                            description=f"Field '{fname}' tag changed from {finfo1['tag']} to {finfo2['tag']}. Wire format incompatibility with existing serialized messages.",
                            old_value=str(finfo1["tag"]),
                            new_value=str(finfo2["tag"])
                        ))
                    # Type changed
                    if finfo1["type"] != finfo2["type"]:
                        changes.append(ContractChange(
                            category="BREAKING",
                            contract_type="Protobuf",
                            entity_path=f"{mname}.{fname}",
                            change_type="TYPE_CHANGED",
                            description=f"Field '{fname}' type changed from '{finfo1['type']}' to '{finfo2['type']}'. Wire deserialization failure.",
                            old_value=finfo1["type"],
                            new_value=finfo2["type"]
                        ))
                    # Cardinality changed (scalar vs repeated)
                    if finfo1["rule"] != finfo2["rule"]:
                        changes.append(ContractChange(
                            category="BREAKING",
                            contract_type="Protobuf",
                            entity_path=f"{mname}.{fname}",
                            change_type="CARDINALITY_CHANGED",
                            description=f"Field '{fname}' rule changed from '{finfo1['rule']}' to '{finfo2['rule']}'.",
                            old_value=finfo1["rule"],
                            new_value=finfo2["rule"]
                        ))

            for fname, finfo2 in fields2.items():
                if fname not in fields1 and finfo2["tag"] not in tag_to_field1:
                    changes.append(ContractChange(
                        category="ADDITIVE",
                        contract_type="Protobuf",
                        entity_path=f"{mname}.{fname}",
                        change_type="FIELD_ADDED",
                        description=f"New field '{fname}: {finfo2['type']} = {finfo2['tag']}' added to message '{mname}'. Backward-compatible with older clients.",
                        old_value=None,
                        new_value=f"{finfo2['type']} = {finfo2['tag']}"
                    ))

        return changes
