import json
import re
from pathlib import Path
from collections import defaultdict

# --- Configuration ---
INDEX_JSON_PATH = None  # Will be set after ROOT_DIR
ROOT_DIR = Path(__file__).parent.parent.parent.resolve()
SHARED_DEFS_PATH = ROOT_DIR / "definitions" / "shared.json"
TOPICS_DIR = ROOT_DIR / "topics"
INDEX_JSON_PATH = TOPICS_DIR / "index.json"

# Regex for finding term references: {term:key:display}
TERM_REF_PATTERN = re.compile(r"\{term:([^:]+):([^}]+)\}")
# Regex for validating hex color codes
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class validator:
    def __init__(self):
        # Data storage
        self.shared_data = {"popups": {}, "terms": {}, "palette": {}}
        self.topic_data = {}  # {filename: {"popups": {}, "terms": {}, "palette": {}}}

        self.issues = []  # List of {"file": str, "level": str, "message": str, "context": str}

    def log(self, file, level, message, context=""):
        self.issues.append(
            {"file": str(file), "level": level, "message": message, "context": context}
        )

    def load_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.log(path, "FATAL", f"Failed to load JSON: {e}")
            return None

    def load_all_data(self):
        # Load shared definitions
        data = self.load_json(SHARED_DEFS_PATH)
        if data:
            self.shared_data["popups"] = data.get("popups", {})
            self.shared_data["terms"] = data.get("terms", {})
            self.shared_data["palette"] = data.get("colorPalette", {})

        # Load topic definitions
        term_files = list(TOPICS_DIR.glob("*.json"))
        for p in term_files:
            if p.name == "index.json" or p.name == "_template.json":
                continue
            data = self.load_json(p)
            if data:
                self.topic_data[p.name] = {
                    "popups": data.get("popups", {}),
                    "terms": data.get("terms", {}),
                    "palette": data.get("colorPalette", {}),
                }

    def resolve_term(self, key, origin_file=None):
        """
        Resolve a reference key (from {term:key:...}) to a popup definition.
        STRICT: key -> popup (No aliases, No popupKey indirection)
        """
        # 1. Look up the definition using the key directly
        # Check Local Popups
        if origin_file and origin_file in self.topic_data:
            if key in self.topic_data[origin_file]["popups"]:
                return self.topic_data[origin_file]["popups"][key], origin_file

        # Check Shared Popups
        if key in self.shared_data["popups"]:
            return self.shared_data["popups"][key], "shared.json"

        return None, None

    def resolve_palette(self, color_key, origin_file=None):
        """Find color hex looking in local file first, then shared."""
        if origin_file and origin_file in self.topic_data:
            if color_key in self.topic_data[origin_file]["palette"]:
                return self.topic_data[origin_file]["palette"][color_key]

        if color_key in self.shared_data["palette"]:
            return self.shared_data["palette"][color_key]

        return None

    def validate_popup_structure(self, popups, file_path):
        """Check if popups follow the strict structure from README"""
        if not popups:
            return

        for key, popup in popups.items():
            # 1. Check title
            if "title" not in popup or not popup["title"].strip():
                self.log(
                    file_path,
                    "ERROR",
                    f"Popup '{key}' missing required 'title'",
                    f"popups.{key}",
                )

            # 2. Check color (REMOVED - Color is now derived or auto-generated)
            # if "color" not in popup: ...

            # 3. Check Sections
            if "sections" not in popup or not isinstance(popup["sections"], list):
                self.log(
                    file_path,
                    "ERROR",
                    f"Popup '{key}' missing 'sections' list",
                    f"popups.{key}",
                )
                continue

            has_intuitive = False
            has_scientific = False
            has_example = False
            has_divider = False

            sections = popup["sections"]
            for i, section in enumerate(sections):
                sType = section.get("type")
                context = f"popups.{key}.sections[{i}]"

                if "content" in section:
                    self.validate_recursive_content(
                        section["content"], file_path, context
                    )

                if sType == "intuitive":
                    has_intuitive = True
                    # Check for lack of detail? Hard to automate.
                    # Check for mathy stuff in intuitive?
                    if "formula" in section:
                        self.log(
                            file_path,
                            "WARNING",
                            f"Intuitive section for '{key}' shouldn't have formal 'formula'",
                            context,
                        )

                elif sType == "scientific":
                    has_scientific = True
                    if "formula" not in section or not section["formula"].strip():
                        self.log(
                            file_path,
                            "ERROR",
                            f"Scientific section for '{key}' missing 'formula' field",
                            context,
                        )
                    else:
                        self.validate_recursive_content(
                            section["formula"], file_path, f"{context}.formula"
                        )

                elif sType == "example":
                    has_example = True
                    content = section.get("content", "")
                    if (
                        "code-block" not in content
                        and "insight-box" not in content
                        and len(content) < 50
                    ):
                        self.log(
                            file_path,
                            "WARNING",
                            f"Example section for '{key}' seems empty or weak (no code/insight box)",
                            context,
                        )

                elif sType == "divider":
                    has_divider = True

            # Structure Checks
            if not has_intuitive:
                self.log(
                    file_path,
                    "ERROR",
                    f"Popup '{key}' missing 'intuitive' section",
                    f"popups.{key}",
                )
            if not has_scientific:
                self.log(
                    file_path,
                    "ERROR",
                    f"Popup '{key}' missing 'scientific' section",
                    f"popups.{key}",
                )
            if not has_example:
                self.log(
                    file_path,
                    "WARNING",
                    f"Popup '{key}' missing 'example' section (Recommended)",
                    f"popups.{key}",
                )

            if len(sections) > 1 and not has_divider:
                self.log(
                    file_path,
                    "WARNING",
                    f"Popup '{key}' has multiple sections but no dividers",
                    f"popups.{key}",
                )

    def validate_text_equations(self, text, file_path, context):
        """
        Check if text contains "loose" equations that should be in an equation box.
        Heuristic: contains equals/approx/arrows surrounded by "mathy" tokens.
        """
        # Skip if it's explicitly a formula field (caller handles this context check)
        if "formula" in context or "equation" in context:
            return

        # Math operators to check
        ops = ["=", "≈", "→", "≥", "≤"]

        # Heuristic: Is a token "mathy"?
        # Mathy: {term:...}, Number, Single Letter, Greek Char, or known math function
        def is_mathy(token):
            token = token.strip().rstrip(",.").rstrip(";")
            if not token:
                return False
            if token.startswith("{term:") and token.endswith("}"):
                return True
            if re.match(r"^[\d\.]+$", token):
                return True  # Number
            if len(token) == 1 and token.isalpha():
                return True  # Single letter var
            # Removed hyphen '-' to avoid flagging hyphenated words like B-PER
            if any(x in token for x in ["(", ")", "+", "*", "/"]):
                return True  # Math chars
            return False

        # We scan the text for operators
        # This is a simple tokenizer approach
        for op in ops:
            if op not in text:
                continue

            # Split by operator to check neighbors
            parts = text.split(op)
            for i in range(len(parts) - 1):
                lhs = parts[i].split()[-1] if parts[i].split() else ""
                rhs = parts[i + 1].split()[0] if parts[i + 1].split() else ""

                # If BOTH neighbors look mathy, it's likely an equation
                if is_mathy(lhs) and is_mathy(rhs):
                    self.log(
                        file_path,
                        "WARNING",
                        "Potential loose equation: '{} {} {}'".format(lhs, op, rhs),
                        "Found in text. Should likely be in 'equation' block.",
                    )
                    return  # Log once per text block to avoid spam
                break

    def validate_text_code(self, text, file_path, context):
        """
        Check for loose Python code that should be in a code-block.
        Heuristic: Keywords (def, class, return, import) found WITHOUT surrounding <code..> tags.
        """
        if "code-block" in context:  # Already checked or inside known block
            return

        # Patterns to check
        # \b ensures word boundary.
        patterns = [
            r"\bdef\s+\w+\(",  # def func(
            r"\bclass\s+\w+:",  # class Name:
            r"\bimport\s+\w+",  # import module
            r"\breturn\s+",  # return val
            r"print\(",  # print(
            r"\.append\(",  # .append(
            # Literal Data Structures
            r"\[\s*[^\]]+,\s*[^\]]+\]",  # [a, b]
            r"\{\s*[^}]+:[^}]+,[^}]+\}",  # {k: v, ...}
            # Tuple: (val, val) - strict to avoid English text like "(see below, section A)"
            r"\((?:(?:['\"]\w+['\"]|\d+|[a-zA-Z_]\w*)\s*,\s*)+(?:['\"]\w+['\"]|\d+|[a-zA-Z_]\w*)\)",
            # Method Calls: object.method(
            r"\b[a-zA-Z_]\w*\.[a-zA-Z_]\w*\(",
            # Function Calls: func(
            r"\b[a-zA-Z_]\w*\(",
        ]

        for pat in patterns:
            if re.search(pat, text):
                # Check if likely inside a code tag
                if "<code" not in text and "```" not in text:
                    self.log(
                        file_path,
                        "WARNING",
                        f"Potential loose code (matched '{pat}')",
                        f"'{text[:50]}...'. Code should be in a 'code-block' or <code> inline tag",
                    )
                    return  # Log once

    def validate_references(self, text, file_path, context):
        if not isinstance(text, str):
            return

        matches = TERM_REF_PATTERN.findall(text)
        for key, display in matches:
            popup, origin = self.resolve_term(key, Path(file_path).name)
            if not popup:
                self.log(
                    file_path,
                    "ERROR",
                    f"Orphan reference found: 'term:{key}'",
                    f"{context} -> ...{text[max(0, text.find(key) - 20) : min(len(text), text.find(key) + 20)]}...",
                )

    def validate_recursive_content(
        self, data, file_path, context="", skip_eq_check=False
    ):
        """Recursively scan JSON for strings to find references"""
        if isinstance(data, dict):
            # Check if this dict itself is an equation block to skip internal text check?
            # If type is "equation", we might skip 'validate_text_equations' on its children but still check references.
            is_equation_block = (
                data.get("type") == "equation" or "formula" in context or skip_eq_check
            )
            # If type is "code-block", skip code checks
            is_code_block = data.get("type") == "code-block"

            for k, v in data.items():
                new_ctx = f"{context}.{k}"
                if is_equation_block:
                    # deeply check references but skip equation-in-text check
                    self.validate_recursive_content(
                        v, file_path, new_ctx, skip_eq_check=True
                    )
                elif is_code_block:
                    # Skip text/code validation deeply, just ref checks? Reference checks in code block?
                    # Code might have comments with refs? Supported?
                    # Safe to check references in code blocks? Yes.
                    self.validate_recursive_content(
                        v, file_path, new_ctx, skip_eq_check=True
                    )
                else:
                    self.validate_recursive_content(v, file_path, new_ctx)

        elif isinstance(data, list):
            for i, v in enumerate(data):
                self.validate_recursive_content(
                    v, file_path, f"{context}[{i}]", skip_eq_check=skip_eq_check
                )

        elif isinstance(data, str):
            self.validate_references(data, file_path, context)

            # Context-based skips
            is_formula = context.endswith("formula") or "equation" in context

            if not skip_eq_check and not is_formula:
                self.validate_text_equations(data, file_path, context)
                self.validate_text_code(data, file_path, context)

    def check_duplicates(self):
        """
        Check for duplicates loosely:
        If a term key matches another term's key, symbol, or popup title (normalized).
        """
        # Gather all terms/popups global lookup
        # normalized_str -> [(origin_file, type, key, actual_str)]
        lookup = defaultdict(list)

        def normalize(s):
            return str(s).lower().strip().replace("-", " ").replace("_", " ")

        # 1. Index Shared
        for key, popup in self.shared_data["popups"].items():
            norm_k = normalize(key)
            lookup[norm_k].append(("shared.json", "popup_key", key, key))
            if "title" in popup:
                norm_t = normalize(popup["title"])
                lookup[norm_t].append(
                    ("shared.json", "popup_title", key, popup["title"])
                )

        for key, term in self.shared_data["terms"].items():
            norm_k = normalize(key)
            lookup[norm_k].append(("shared.json", "term_key", key, key))
            if "display" in term:
                norm_d = normalize(term["display"])
                lookup[norm_d].append(
                    ("shared.json", "term_symbol", key, term["display"])
                )

        # 2. Check Topics against Lookup
        for filename, data in self.topic_data.items():
            # Check Term Keys & Symbols
            for key, term in data["terms"].items():
                checks = [
                    (normalize(key), "term_key", key),
                ]
                if "display" in term:
                    checks.append(
                        (normalize(term["display"]), "term_symbol", term["display"])
                    )

                for norm_val, dtype, actual_val in checks:
                    if norm_val in lookup:
                        # Filter out matches from same file (not duplicate if local)
                        # actually we care if it matches SHARED or OTHER topics
                        matches = [m for m in lookup[norm_val] if m[0] != filename]
                        if matches:
                            # format warning
                            match_desc = ", ".join(
                                [f"{m[0]}:{m[1]}='{m[3]}'" for m in matches[:3]]
                            )
                            self.log(
                                Path(TOPICS_DIR) / filename,
                                "WARNING",
                                f"Potential Duplicate: Local {dtype} '{actual_val}' matches existing concepts",
                                f"Matches: {match_desc}",
                            )

            # Check Popup Keys & Titles
            for key, popup in data["popups"].items():
                checks = [
                    (normalize(key), "popup_key", key),
                ]
                if "title" in popup:
                    checks.append(
                        (normalize(popup["title"]), "popup_title", popup["title"])
                    )

                for norm_val, dtype, actual_val in checks:
                    if norm_val in lookup:
                        matches = [m for m in lookup[norm_val] if m[0] != filename]
                        if matches:
                            match_desc = ", ".join(
                                [f"{m[0]}:{m[1]}='{m[3]}'" for m in matches[:3]]
                            )
                            self.log(
                                Path(TOPICS_DIR) / filename,
                                "WARNING",
                                f"Potential Duplicate: Local {dtype} '{actual_val}' matches existing concepts",
                                f"Matches: {match_desc}",
                            )

            # Update lookup with this topic's content (so subsequent topics check against this one)
            for key, popup in data["popups"].items():
                norm_k = normalize(key)
                lookup[norm_k].append((filename, "popup_key", key, key))
                if "title" in popup:
                    norm_t = normalize(popup["title"])
                    lookup[norm_t].append(
                        (filename, "popup_title", key, popup["title"])
                    )

            for key, term in data["terms"].items():
                norm_k = normalize(key)
                lookup[norm_k].append((filename, "term_key", key, key))
                if "display" in term:
                    norm_d = normalize(term["display"])
                    lookup[norm_d].append(
                        (filename, "term_symbol", key, term["display"])
                    )

    def validate_consistency(self):
        """Check consistency between 'terms' and 'popups' and 'colorPalette'"""

        def check_set(terms, popups, palette, file_name):
            for key, term_data in terms.items():
                context = f"terms.{key}"

                # 1. Check for LEGACY fields (Strict Migration)
                if "popupKey" in term_data:
                    self.log(
                        file_name,
                        "ERROR",
                        f"Legacy field 'popupKey' detected in term '{key}'",
                        "Remove it. Rule: Term Key MUST match Popup Key.",
                    )

                if "colorKey" in term_data:
                    self.log(
                        file_name,
                        "ERROR",
                        f"Legacy field 'colorKey' detected in term '{key}'",
                        "Remove it. Rule: Term Key MUST match Color Key (if manual).",
                    )

                # 2. Check if popup exists (Key = PopupKey)
                # We use resolve_term which now strictly uses 'key'
                popup, origin = self.resolve_term(key, file_name)
                if not popup:
                    self.log(
                        file_name,
                        "ERROR",
                        f"Term '{key}' missing definition",
                        f"Expected popup with key '{key}' in 'popups' (shared or local).",
                    )

                # 3. Check color consistency (if manual color exists)
                # We check if the key exists in the palette (local or shared)
                hex_color = self.resolve_palette(key, file_name)

                # Note: valid to NOT have a palette entry (auto-generated)
                # But if it HAS a palette entry, it must match any manual color in popup (if that even exists anymore?)
                # Actually, popups shouldn't have 'color' field either?
                # The script earlier checks popup['color'] vs palette.
                # Let's check popup['color'] if it exists.

                if popup and "color" in popup:
                    # Popups having 'color' field is also kinda legacy info duplication if strict?
                    # But README says "No color field needed!".
                    # Let's warn if it mismatches palette or auto-gen?
                    # For now, let's just check if it matches PALETTE if palette exists.
                    if hex_color and popup.get("color").lower() != hex_color.lower():
                        self.log(
                            file_name,
                            "WARNING",
                            f"Color Mismatch for '{key}': Palette '{key}' ({hex_color}) != Popup 'color' ({popup.get('color')})",
                            context,
                        )

        # Check shared
        check_set(
            self.shared_data["terms"],
            self.shared_data["popups"],
            self.shared_data["palette"],
            "shared.json",
        )

        # Check topics
        for fname, data in self.topic_data.items():
            check_set(data["terms"], data["popups"], data["palette"], fname)

    def get_popup_status(self, popup_data):
        """Analyze a popup and return presence of key components boolean tuple"""
        has_int = False
        has_sci = False
        has_form = False
        has_ex = False

        if popup_data:
            for section in popup_data.get("sections", []):
                sType = section.get("type")
                if sType == "intuitive":
                    has_int = True
                if sType == "scientific":
                    has_sci = True
                    if "formula" in section and section["formula"].strip():
                        has_form = True
                if sType == "example":
                    has_ex = True

        return has_int, has_sci, has_form, has_ex

    def report_terms(self):
        print("\n" + "=" * 160)
        print(
            f"{'TERM KEY':<20} | {'ORIGIN':<20} | {'SYMBOL':<8} | {'COLOR':<8} | {'INT':<4} | {'SCI':<4} | {'EQ':<4} | {'EX':<4} | {'POPUP TITLE'}"
        )
        print("=" * 160)

        all_terms = []

        # Helper to collect term data
        def collect_term(key, term_data, origin_file):
            # Resolve popup using strict key
            popup_data, popup_origin = self.resolve_term(key, origin_file)

            h_int, h_sci, h_form, h_ex = self.get_popup_status(popup_data)

            # Get color (strict key)
            color = self.resolve_palette(key, origin_file)

            return {
                "key": key,
                "origin": origin_file,
                "symbol": term_data.get("display", "?"),
                "title": popup_data.get("title", "MISSING POPUP")
                if popup_data
                else "MISSING POPUP",
                "color": color or "Auto/None",
                "status": (h_int, h_sci, h_form, h_ex),
            }

        # Collect Shared
        for key, data in self.shared_data["terms"].items():
            all_terms.append(collect_term(key, data, "shared.json"))

        # Collect Topics
        for fname, tdata in self.topic_data.items():
            for key, data in tdata["terms"].items():
                all_terms.append(collect_term(key, data, fname))

        # Sort and Print
        all_terms.sort(key=lambda x: (x["origin"], x["key"]))

        for t in all_terms:
            s = t["status"]
            # Formatting checks
            int_mark = "✅" if s[0] else "❌"
            sci_mark = "✅" if s[1] else "❌"
            eq_mark = "✅" if s[2] else "❌"
            ex_mark = "✅" if s[3] else "❌"

            print(
                f"{t['key']:<20} | {t['origin']:<20} | {t['symbol']:<8} | {t['color']:<8} | {int_mark:<4} | {sci_mark:<4} | {eq_mark:<4} | {ex_mark:<4} | {t['title']}"
            )
        print("=" * 160)

    def validate_uniqueness(self):
        """
        Check for:
        1. Duplicate Popup Keys (Collision between Topic A and Topic B).
        2. Duplicate Titles (Different keys having same title).
        3. Duplicate Colors (Different colorKeys having same HEX value).
        """

        # Maps for collision detection
        # Key -> [files defining it]
        key_definitions = defaultdict(list)
        # Title -> [keys using it]
        title_usage = defaultdict(list)
        # Hex -> [colorKeys using it]
        color_usage = defaultdict(list)

        # 1. Collect from Shared
        for key, popup in self.shared_data["popups"].items():
            key_definitions[key].append("shared.json")
            if "title" in popup:
                title_usage[popup["title"].strip()].append(f"{key} (shared)")

        for key, hex_val in self.shared_data["palette"].items():
            color_usage[hex_val.lower()].append(f"{key} (shared)")

        # 2. Collect from Topics
        for fname, data in self.topic_data.items():
            # Popups
            for key, popup in data["popups"].items():
                key_definitions[key].append(fname)
                if "title" in popup:
                    title_usage[popup["title"].strip()].append(f"{key} ({fname})")

            # Palette
            for key, hex_val in data["palette"].items():
                color_usage[hex_val.lower()].append(f"{key} ({fname})")

        # 3. Analyze Collisions

        # Duplicate Keys
        for key, files in key_definitions.items():
            if len(files) > 1:
                # If shared is one of them, we already warned in check_duplicates (override).
                # But if it's two topics, that's a collision.
                # If Shared + Topic, that's an override (Warning).
                # If Topic A + Topic B, that's a Conflict (Error).

                topics = [f for f in files if f != "shared.json"]

                if len(topics) > 1:
                    self.log(
                        "GLOBAL",
                        "ERROR",
                        f"Duplicate Popup Definition: '{key}'",
                        f"Defined in multiple topics: {topics}",
                    )

        # Duplicate Titles
        for title, keys in title_usage.items():
            if len(keys) > 1:
                self.log(
                    "GLOBAL",
                    "WARNING",
                    f"Duplicate Popup Title: '{title}'",
                    f"Used by keys: {keys}",
                )

        # Duplicate Colors (Hex Collision)
        for hex_val, keys in color_usage.items():
            if len(keys) > 1:
                self.log(
                    "GLOBAL",
                    "ERROR",
                    f"Color Collision: Hex '{hex_val}' used by multiple keys",
                    f"Keys: {keys}. Rule: One Color Per Concept (Bijective Mapping Required).",
                )

        # 4. Check for ALIASES (Multiple Terms -> Same Popup Key)
        # With STRICT Key=PopupKey, this is impossible unless multiple terms are somehow defined
        # but we already iterate keys.

        # 5. Check for Ambiguous Symbols (Multiple Terms -> Same Display Symbol)
        # Example: {"key1": "P", "key2": "P"} -> Confusing
        # Example: {"key1": "P", "key2": "p"} -> Confusing (case insensitive check)

        symbol_usage = defaultdict(list)

        def collect_symbols(terms_dict, source):
            for key, data in terms_dict.items():
                if "display" in data:
                    symbol = data["display"].strip()
                    # Use lower case to catch P vs p ambiguity
                    norm_sym = symbol.lower()
                    symbol_usage[norm_sym].append(f"{key} ('{symbol}' in {source})")

        # Collect Shared
        collect_symbols(self.shared_data.get("terms", {}), "shared.json")

        # Collect Topics
        for fname, data in self.topic_data.items():
            collect_symbols(data.get("terms", {}), fname)

        # Check for collisions
        for norm_sym, usages in symbol_usage.items():
            if len(usages) > 1:
                # We need to check if these usages are from DIFFERENT keys.
                # If the same key is defined in shared and then overridden in topic with same symbol, that's fine.
                # Parse keys from usage strings: "key (...)"
                keys_involved = set()
                for u in usages:
                    k = u.split(" ")[0]
                    keys_involved.add(k)

                if len(keys_involved) > 1:
                    self.log(
                        "GLOBAL",
                        "WARNING",
                        f"Ambiguous Symbol: '{norm_sym}' (or variant)",
                        f"Used by distinct concepts: {usages}. Users might get confused.",
                    )

    # ========================================================================
    # NEW ROBUST VALIDATIONS
    # ========================================================================

    def validate_hex_colors(self):
        """Validate all color hex codes are valid #RRGGBB format."""
        # Check shared palette
        for key, hex_val in self.shared_data["palette"].items():
            if not HEX_COLOR_PATTERN.match(hex_val):
                self.log(
                    SHARED_DEFS_PATH,
                    "ERROR",
                    f"Invalid hex color for palette key '{key}': '{hex_val}'",
                    "Must be #RRGGBB format (6 hex digits)",
                )

        # Check shared popup colors
        for key, popup in self.shared_data["popups"].items():
            color = popup.get("color", "")
            if color and not HEX_COLOR_PATTERN.match(color):
                self.log(
                    SHARED_DEFS_PATH,
                    "ERROR",
                    f"Invalid hex color in popup '{key}': '{color}'",
                    "Must be #RRGGBB format (6 hex digits)",
                )

        # Check topic palettes and popups
        for filename, data in self.topic_data.items():
            full_path = TOPICS_DIR / filename
            for key, hex_val in data["palette"].items():
                if not HEX_COLOR_PATTERN.match(hex_val):
                    self.log(
                        full_path,
                        "ERROR",
                        f"Invalid hex color for palette key '{key}': '{hex_val}'",
                        "Must be #RRGGBB format (6 hex digits)",
                    )
            for key, popup in data["popups"].items():
                color = popup.get("color", "")
                if color and not HEX_COLOR_PATTERN.match(color):
                    self.log(
                        full_path,
                        "ERROR",
                        f"Invalid hex color in popup '{key}': '{color}'",
                        "Must be #RRGGBB format (6 hex digits)",
                    )

    def validate_html_tags(self, text, file_path, context):
        """
        Check for unbalanced HTML tags in content strings.
        Only checks common inline/block tags used in the blog content.
        """
        if not isinstance(text, str) or not text.strip():
            return

        # Tags commonly used in the blog content (self-closing tags excluded)
        tags_to_check = [
            "strong",
            "em",
            "code",
            "ul",
            "ol",
            "li",
            "br",
            "span",
            "div",
            "p",
            "a",
            "table",
            "tr",
            "td",
            "th",
            "thead",
            "tbody",
        ]

        for tag in tags_to_check:
            # Count opening and closing tags (case insensitive)
            open_pattern = re.compile(rf"<{tag}(\s[^>]*)?>", re.IGNORECASE)
            close_pattern = re.compile(rf"</{tag}>", re.IGNORECASE)

            open_count = len(open_pattern.findall(text))
            close_count = len(close_pattern.findall(text))

            # Skip <br> and other self-closing tags
            if tag == "br":
                continue

            if open_count != close_count:
                self.log(
                    file_path,
                    "ERROR",
                    f"Unbalanced HTML tags: <{tag}> opened {open_count}x, closed {close_count}x",
                    f"{context}",
                )

    def validate_index_json(self):
        """Validate topics/index.json structure and paths."""
        if not INDEX_JSON_PATH.exists():
            self.log(
                INDEX_JSON_PATH,
                "ERROR",
                "topics/index.json does not exist",
                "Topic picker will fail to load",
            )
            return

        data = self.load_json(INDEX_JSON_PATH)
        if not data:
            return

        if "topics" not in data or not isinstance(data["topics"], list):
            self.log(
                INDEX_JSON_PATH,
                "ERROR",
                "Missing 'topics' array in index.json",
                "root",
            )
            return

        seen_ids = set()
        for i, topic in enumerate(data["topics"]):
            context = f"topics[{i}]"

            # Check required fields
            for field in ["id", "title", "description", "path"]:
                if field not in topic or not str(topic.get(field, "")).strip():
                    self.log(
                        INDEX_JSON_PATH,
                        "ERROR",
                        f"Topic {i} missing required field '{field}'",
                        context,
                    )

            # Check for duplicate IDs
            topic_id = topic.get("id", "")
            if topic_id in seen_ids:
                self.log(
                    INDEX_JSON_PATH,
                    "ERROR",
                    f"Duplicate topic ID: '{topic_id}'",
                    context,
                )
            seen_ids.add(topic_id)

            # Check if path exists
            topic_path = topic.get("path", "")
            if topic_path:
                full_path = ROOT_DIR / topic_path
                if not full_path.exists():
                    self.log(
                        INDEX_JSON_PATH,
                        "ERROR",
                        f"Topic path does not exist: '{topic_path}'",
                        context,
                    )

    def validate_navigation_structure(self, data, file_path):
        """Validate navigation.sections reference valid slide IDs."""
        if "navigation" not in data or "slides" not in data:
            return  # Skip files without navigation structure

        nav = data.get("navigation", {})
        slides_list = data.get("slides", [])

        if "sections" not in nav:
            return

        # slides is a list of objects with "id" field, not a dict
        if isinstance(slides_list, list):
            all_slide_ids = {
                slide.get("id")
                for slide in slides_list
                if isinstance(slide, dict) and "id" in slide
            }
        else:
            # If it's somehow a dict, handle gracefully
            all_slide_ids = (
                set(slides_list.keys()) if isinstance(slides_list, dict) else set()
            )

        referenced_slides = set()

        for sec_idx, section in enumerate(nav["sections"]):
            sec_context = f"navigation.sections[{sec_idx}]"

            # Check section has required fields
            if "id" not in section:
                self.log(
                    file_path,
                    "ERROR",
                    f"Navigation section {sec_idx} missing 'id' field",
                    sec_context,
                )
            if "title" not in section or not section.get("title", "").strip():
                self.log(
                    file_path,
                    "ERROR",
                    f"Navigation section {sec_idx} missing 'title' field",
                    sec_context,
                )
            if "slides" not in section or not isinstance(section.get("slides"), list):
                self.log(
                    file_path,
                    "ERROR",
                    f"Navigation section {sec_idx} missing 'slides' array",
                    sec_context,
                )
                continue

            # Check each slide reference
            for slide_id in section.get("slides", []):
                referenced_slides.add(slide_id)
                if slide_id not in all_slide_ids:
                    self.log(
                        file_path,
                        "ERROR",
                        f"Navigation references non-existent slide: '{slide_id}'",
                        sec_context,
                    )

        # Check for orphan slides (defined but not in navigation)
        orphan_slides = all_slide_ids - referenced_slides
        if orphan_slides:
            self.log(
                file_path,
                "WARNING",
                f"Slides defined but not in navigation: {sorted(orphan_slides)}",
                "Check if these are intentionally orphaned",
            )

    def validate_empty_content(self, data, file_path, context="root"):
        """
        Recursively check for empty or whitespace-only content fields.
        Note: popup section 'title' is OPTIONAL per README (scientific sections often omit it).
        We only flag critical empty fields that would cause issues.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                new_ctx = f"{context}.{key}"

                # Check specific fields that should never be empty
                # Note: 'title' in popup sections is OPTIONAL - skip it
                # Only required: popup-level title, content, formula when expected
                is_popup_section_title = (
                    key == "title" and ".sections[" in context and ".popups." in context
                )

                if key in ["content", "formula"] and isinstance(value, str):
                    if not value.strip():
                        self.log(
                            file_path,
                            "ERROR",
                            f"Empty '{key}' field",
                            new_ctx,
                        )
                # Only flag empty title if it's NOT a popup section title
                elif (
                    key == "title"
                    and isinstance(value, str)
                    and not is_popup_section_title
                ):
                    if not value.strip():
                        self.log(
                            file_path,
                            "ERROR",
                            f"Empty '{key}' field",
                            new_ctx,
                        )

                self.validate_empty_content(value, file_path, new_ctx)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                self.validate_empty_content(item, file_path, f"{context}[{i}]")

    def validate_unused_definitions(self):
        """
        Detect popups, terms, and colors that are defined but never referenced.
        Only checks within each file's scope (not cross-file for performance).
        """
        # Collect all term references from topic content
        for filename in self.topic_data:
            full_path = TOPICS_DIR / filename
            data = self.load_json(full_path)
            if not data:
                continue

            # Track what's used in content
            used_term_refs = set()

            def collect_refs(obj):
                if isinstance(obj, str):
                    matches = TERM_REF_PATTERN.findall(obj)
                    for key, display in matches:
                        used_term_refs.add(key)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        collect_refs(v)
                elif isinstance(obj, list):
                    for item in obj:
                        collect_refs(item)

            # Scan slides for term refs
            if "slides" in data:
                collect_refs(data["slides"])

            # Check for unused terms (terms defined but never {term:key:...} in content)
            local_terms = self.topic_data[filename].get("terms", {})
            for term_key in local_terms:
                if term_key not in used_term_refs:
                    # Check if it's actually referenced in slides
                    self.log(
                        full_path,
                        "WARNING",
                        f"Term '{term_key}' defined but never referenced in content",
                        "Consider removing if unused",
                    )

            # Check for unused palette colors
            local_palette = self.topic_data[filename].get("palette", {})
            used_color_keys = {
                t.get("colorKey") for t in local_terms.values() if "colorKey" in t
            }
            for color_key in local_palette:
                if color_key not in used_color_keys:
                    self.log(
                        full_path,
                        "WARNING",
                        f"Palette color '{color_key}' defined but not used by any term",
                        "Consider removing if unused",
                    )

    def validate_popup_color_consistency(self):
        """
        Ensure popup 'color' field matches the resolved colorKey from the term.
        This catches mismatches where popup says #AAA but term's colorKey resolves to #BBB.
        """
        # Check shared terms
        for term_key, term_data in self.shared_data["terms"].items():
            popup_key = term_data.get("popupKey")
            color_key = term_data.get("colorKey")

            if not popup_key or not color_key:
                continue

            popup = self.shared_data["popups"].get(popup_key)
            palette_color = self.shared_data["palette"].get(color_key)

            if popup and palette_color:
                popup_color = popup.get("color", "")
                if popup_color.lower() != palette_color.lower():
                    self.log(
                        SHARED_DEFS_PATH,
                        "ERROR",
                        f"Color mismatch for term '{term_key}': popup '{popup_key}' has color '{popup_color}' but colorKey '{color_key}' maps to '{palette_color}'",
                        "Popup color and palette color should match",
                    )

        # Check topic terms
        for filename, data in self.topic_data.items():
            full_path = TOPICS_DIR / filename
            for term_key, term_data in data["terms"].items():
                popup_key = term_data.get("popupKey")
                color_key = term_data.get("colorKey")

                if not popup_key or not color_key:
                    continue

                # Resolve popup (local first, then shared)
                popup = data["popups"].get(popup_key) or self.shared_data["popups"].get(
                    popup_key
                )
                # Resolve color (local first, then shared)
                palette_color = data["palette"].get(color_key) or self.shared_data[
                    "palette"
                ].get(color_key)

                if popup and palette_color:
                    popup_color = popup.get("color", "")
                    if popup_color.lower() != palette_color.lower():
                        self.log(
                            full_path,
                            "ERROR",
                            f"Color mismatch for term '{term_key}': popup '{popup_key}' has color '{popup_color}' but colorKey '{color_key}' maps to '{palette_color}'",
                            "Popup color and palette color should match",
                        )

    def validate_formula_quality(self, popups, file_path):
        """
        Check that scientific section formulas contain term references.
        A formula with no {term:...} defeats the purpose of interactive equations.
        """
        for key, popup in popups.items():
            for i, section in enumerate(popup.get("sections", [])):
                if section.get("type") != "scientific":
                    continue

                formula = section.get("formula", "")
                if not formula.strip():
                    continue  # Already caught by structure validation

                # Check if formula has at least one term reference
                if not TERM_REF_PATTERN.search(formula):
                    self.log(
                        file_path,
                        "WARNING",
                        f"Formula in popup '{key}' has no interactive term references",
                        f"popups.{key}.sections[{i}].formula - Consider adding {{term:key:display}} for interactivity",
                    )

    def validate_meta_fields(self, data, file_path):
        """Validate required meta fields in topic files."""
        if "meta" not in data:
            self.log(
                file_path,
                "WARNING",
                "Missing 'meta' section",
                "Should have title, subtitle, version",
            )
            return

        meta = data["meta"]
        required = ["title"]
        recommended = ["subtitle", "version"]

        for field in required:
            if field not in meta or not str(meta.get(field, "")).strip():
                self.log(
                    file_path,
                    "ERROR",
                    f"Missing required meta field: '{field}'",
                    "meta",
                )

        for field in recommended:
            if field not in meta or not str(meta.get(field, "")).strip():
                self.log(
                    file_path,
                    "WARNING",
                    f"Missing recommended meta field: '{field}'",
                    "meta",
                )

    def validate_html_content_deep(self, data, file_path, context="root"):
        """Recursively validate HTML in all string content."""
        if isinstance(data, dict):
            for key, value in data.items():
                new_ctx = f"{context}.{key}"
                if isinstance(value, str) and ("<" in value or ">" in value):
                    self.validate_html_tags(value, file_path, new_ctx)
                else:
                    self.validate_html_content_deep(value, file_path, new_ctx)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self.validate_html_content_deep(item, file_path, f"{context}[{i}]")

    def run(self):
        print("Starting Deep Validation of Blog Content...\n")
        self.load_all_data()

        # ================================================================
        # PHASE 1: Index JSON Validation
        # ================================================================
        print("Validating topics/index.json...")
        self.validate_index_json()

        # ================================================================
        # PHASE 2: Hex Color Validation
        # ================================================================
        print("Validating hex color codes...")
        self.validate_hex_colors()

        # ================================================================
        # PHASE 3: Popup & Term Structure Validation
        # ================================================================
        print("Checking shared.json structure...")
        self.validate_popup_structure(self.shared_data["popups"], SHARED_DEFS_PATH)
        self.validate_formula_quality(self.shared_data["popups"], SHARED_DEFS_PATH)
        shared_full_data = self.load_json(SHARED_DEFS_PATH)
        if shared_full_data:
            self.validate_recursive_content(shared_full_data, SHARED_DEFS_PATH, "root")
            self.validate_empty_content(shared_full_data, SHARED_DEFS_PATH)
            self.validate_html_content_deep(shared_full_data, SHARED_DEFS_PATH)

        print(f"Checking {len(self.topic_data)} topic files...")
        for filename, data in self.topic_data.items():
            full_path = TOPICS_DIR / filename
            full_data = self.load_json(full_path)
            if not full_data:
                continue

            # Structure checks
            self.validate_popup_structure(data["popups"], full_path)
            self.validate_formula_quality(data["popups"], full_path)
            self.validate_recursive_content(full_data, full_path, "root")

            # Meta fields check (only for topic files)
            self.validate_meta_fields(full_data, full_path)

            # Navigation structure check
            self.validate_navigation_structure(full_data, full_path)

            # Empty content check
            self.validate_empty_content(full_data, full_path)

            # HTML balance check
            self.validate_html_content_deep(full_data, full_path)

        # ================================================================
        # PHASE 4: Cross-File Logic Checks
        # ================================================================
        print("Running cross-file logic checks...")
        self.check_duplicates()
        self.validate_consistency()
        self.validate_uniqueness()
        self.validate_popup_color_consistency()
        self.validate_unused_definitions()

        # ================================================================
        # PHASE 5: Report
        # ================================================================
        self.report_terms()

        print("\n" + "=" * 80)
        print("VALIDATION ISSUES REPORT")
        print("=" * 80)

        if not self.issues:
            print("No issues found! Clean as a whistle.")
            return

        # Sort issues: ERROR (Critical) first, then WARNING (Potential)
        self.issues.sort(key=lambda x: (x["level"] != "ERROR", x["file"], x["context"]))

        # Group by file
        issues_by_file = defaultdict(list)
        for issue in self.issues:
            issues_by_file[issue["file"]].append(issue)

        # ANSI Colors
        RED = "\033[91m"
        RESET = "\033[0m"
        YELLOW = "\033[93m"

        for file_path, file_issues in issues_by_file.items():
            print(f"\nFile: {Path(file_path).name}")
            for iss in file_issues:
                if iss["level"] == "ERROR":
                    icon = f"{RED}🔴 [CRITICAL]{RESET}"
                elif iss["level"] == "FATAL":
                    icon = f"{RED}💀 [FATAL]{RESET}"
                else:
                    icon = f"{YELLOW}⚠️  [POTENTIAL]{RESET}"

                print(f"  {icon} {iss['message']}")
                if iss["context"]:
                    print(f"      Context: {iss['context']}")

        print("\n" + "=" * 80)
        error_count = sum(1 for i in self.issues if i["level"] in ("ERROR", "FATAL"))
        warning_count = sum(1 for i in self.issues if i["level"] == "WARNING")

        summary_color = (
            RED if error_count > 0 else (YELLOW if warning_count > 0 else RESET)
        )
        print(
            f"{summary_color}Total Issues: {len(self.issues)} ({error_count} critical, {warning_count} warnings){RESET}"
        )


if __name__ == "__main__":
    v = validator()
    v.run()
