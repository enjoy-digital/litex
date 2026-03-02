#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import re


def parse_port_keyword(kw):
    if "_" not in kw:
        raise ValueError(f"Invalid port '{kw}': expected '<dir>_<path>'")

    d, tail = kw.split("_", 1)
    if d not in ("i", "o", "io"):
        raise ValueError(f"Invalid port '{kw}': must start with i_, o_ or io_")
    if tail == "":
        raise ValueError(f"Invalid port '{kw}': missing path after direction prefix")

    raw_parts = tail.split("_")
    parts = []
    i = 0
    while i < len(raw_parts):
        token = raw_parts[i]
        if token == "":
            if i + 1 >= len(raw_parts) or raw_parts[i + 1] == "":
                raise ValueError(f"Invalid port '{kw}': malformed escaped '_' in path")
            token = "_" + raw_parts[i + 1]
            i += 2
        else:
            i += 1
        if not re.fullmatch(r"_?[A-Za-z][A-Za-z0-9]*", token):
            raise ValueError(f"Invalid port '{kw}': bad path token '{token}'")
        parts.append(token)

    return d, parts


def format_unresolved_port_error(kw, d, parts, wrapper_head, has_submodule, domains, target="converter/module"):
    lines = [
        f"Cannot resolve '{kw}' on {target}.",
        f"- Parsed direction: {d}",
        f"- Parsed path: {'/'.join(parts)}",
        f"- Tried wrapper attribute: '{wrapper_head}'",
    ]
    if has_submodule:
        lines.append(f"- Tried recursive lookup on submodule path: {'/'.join(parts)}")
    if len(parts) >= 2:
        cd_name = "_".join(parts[:-1])
        lines.append(f"- Tried clock-domain signal: domain='{cd_name}', signal='{parts[-1]}'")
    lines.append(f"- Available clock domains: {list(domains)}")
    return "\n".join(lines)


def resolve_output_dir(platform, output_dir):
    if output_dir is None:
        return platform.output_dir
    return output_dir


def resolve_output_paths(platform, output_dir, name):
    base_dir = resolve_output_dir(platform, output_dir)
    src_dir  = os.path.join(base_dir, name)
    v_file   = os.path.join(src_dir, f"{name}.v")
    return src_dir, v_file


def write_text_if_different(path, content):
    old = None
    if os.path.exists(path):
        with open(path, "r") as f:
            old = f.read()
    if old == content:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return True


def normalize_instance_ports(params, *, top_entity, target="converter", generic_prefixes=("p_",)):
    ip_params = dict()
    mapped    = dict()
    for k, v in params.items():
        if any(k.startswith(prefix) for prefix in generic_prefixes):
            continue
        try:
            d, parts = parse_port_keyword(k)
        except ValueError as e:
            raise ValueError(f"Invalid {target} port '{k}' for top '{top_entity}': {e}") from e
        normalized = f"{d}_{'_'.join(parts)}"
        if normalized in mapped:
            raise ValueError(
                f"Ambiguous {target} params: both '{mapped[normalized]}' and '{k}' map to '{normalized}'.")
        mapped[normalized] = k
        ip_params[normalized] = v
    return ip_params


def extract_prefixed_generics(params, *, prefix="p_"):
    return ["-g" + k[len(prefix):] + "=" + str(v) for k, v in params.items() if k.startswith(prefix)]
