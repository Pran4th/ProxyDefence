"""
Phase 0: Complete Dataset Discovery & Inventory
Recursively inspect every file in datasets/ and produce a comprehensive inventory.
"""
import csv
import json
import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DATASETS_DIR = Path(__file__).parent.parent / "datasets"
OUTPUT_DIR = Path(__file__).parent / "inventory"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Add ml-platform to path for parser access
sys.path.insert(0, str(Path(__file__).parent.parent / "services/ml-platform"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def try_read_csv(path, n=1000):
    """Read first n rows of a CSV, return headers, row_count, sample."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = []
            for i, row in enumerate(reader):
                if i < n:
                    rows.append(row)
                if i >= 10000:
                    break
            return {
                "headers": headers,
                "columns": len(headers),
                "rows_sampled": len(rows),
                "total_rows_estimate": i + 1 if rows else 0,
                "sample": rows[:5],
            }
    except Exception as e:
        return {"error": str(e)}


def try_read_excel(path, n=1000):
    """Read first n rows of an Excel file using openpyxl."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        result = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            headers = []
            rows = []
            for i, row in enumerate(ws.iter_row()):
                if i == 0:
                    headers = [cell.value for cell in row]
                elif i <= n:
                    rows.append([cell.value for cell in row])
                if i > 10000:
                    break
            result[sheet_name] = {
                "headers": [str(h) for h in headers if h is not None],
                "columns": len(headers),
                "rows_sampled": len(rows),
            }
        wb.close()
        return result
    except ImportError:
        return {"error": "openpyxl not available"}
    except Exception as e:
        return {"error": str(e)}


def try_read_zip(path):
    """List contents of a ZIP file."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            info = []
            for name in names:
                zi = zf.getinfo(name)
                info.append({
                    "name": name,
                    "size": zi.file_size,
                    "compress_size": zi.compress_size,
                })
            return {"files": info, "count": len(info)}
    except Exception as e:
        return {"error": str(e)}


def infer_type(values):
    """Infer the data type from a list of string values."""
    types = set()
    for v in values:
        if v is None or v == "":
            continue
        v = str(v).strip()
        if not v:
            continue
        try:
            float(v)
            types.add("numeric")
            continue
        except ValueError:
            pass
        if v.lower() in ("true", "false", "yes", "no", "1", "0"):
            types.add("boolean")
            continue
        if len(v) == 10 and v[4] == "-" and v[7] == "-":
            types.add("date")
            continue
        types.add("string")
    if not types:
        return "unknown"
    if "numeric" in types and len(types) == 1:
        return "numeric"
    if "date" in types and len(types) == 1:
        return "date"
    return "string"


def analyze_csv_deep(path, max_rows=50000):
    """Deep analysis of a CSV file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if not headers:
                return {"error": "no headers"}
            
            col_stats = {h: {"nulls": 0, "unique": set(), "total": 0, "values": []} for h in headers}
            row_count = 0
            
            for row in reader:
                row_count += 1
                if row_count > max_rows:
                    break
                for h in headers:
                    v = row.get(h, "")
                    col_stats[h]["total"] += 1
                    if v == "" or v is None:
                        col_stats[h]["nulls"] += 1
                    if len(col_stats[h]["unique"]) < 100:
                        col_stats[h]["unique"].add(v)
                    if len(col_stats[h]["values"]) < 1000:
                        col_stats[h]["values"].append(v)
            
            schema = {}
            for h in headers:
                s = col_stats[h]
                unique_count = len(s["unique"]) if s["unique"] else 0
                null_pct = round(s["nulls"] / max(s["total"], 1) * 100, 2)
                dtype = infer_type(list(s["unique"])[:50])
                schema[h] = {
                    "dtype": dtype,
                    "null_pct": null_pct,
                    "unique_count": unique_count,
                    "cardinality": round(unique_count / max(s["total"], 1), 4),
                }
            
            # Estimate total rows
            file_size = path.stat().st_size
            if row_count > 0:
                avg_row_size = file_size / row_count
                est_total = int(file_size / max(avg_row_size, 1))
            else:
                est_total = 0
            
            return {
                "columns": len(headers),
                "rows_sampled": row_count,
                "estimated_rows": est_total,
                "file_size_bytes": file_size,
                "schema": schema,
            }
    except Exception as e:
        return {"error": str(e)}


def inventory_file(path):
    """Inventory a single file."""
    rel = path.relative_to(DATASETS_DIR)
    suffix = path.suffix.lower()
    size = path.stat().st_size
    
    info = {
        "full_path": str(path),
        "relative_path": str(rel),
        "parent_folder": str(rel.parent),
        "dataset_name": rel.parts[0] if len(rel.parts) > 0 else "",
        "file_format": suffix,
        "file_size_bytes": size,
        "file_size_hr": format_bytes(size),
        "last_modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
    }
    
    if suffix == ".csv":
        info["analysis"] = analyze_csv_deep(path)
    elif suffix in (".xlsx", ".xls"):
        info["analysis"] = try_read_excel(path)
    elif suffix == ".zip":
        info["analysis"] = try_read_zip(path)
    elif suffix == ".txt":
        try:
            info["analysis"] = {"size": size, "preview": path.read_text(encoding="utf-8", errors="replace")[:500]}
        except:
            info["analysis"] = {"error": "cannot read"}
    else:
        info["analysis"] = {"format": suffix, "size": size}
    
    return info


def format_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def is_extractable_format(suffix):
    return suffix in (".zip", ".gz", ".tar", ".tar.gz", ".tgz", ".bz2")


def main():
    print("=" * 80)
    print("PHASE 0: COMPLETE DATASET DISCOVERY & INVENTORY")
    print("=" * 80)
    print(f"Scanning: {DATASETS_DIR}")
    print()
    
    # Walk all files
    all_files = []
    for root, dirs, files in os.walk(DATASETS_DIR):
        for f in files:
            fp = Path(root) / f
            if ".crdownload" in f:
                continue  # incomplete download
            all_files.append(fp)
    
    all_files.sort()
    
    print(f"Found {len(all_files)} files")
    print()
    
    # Inventory each file
    inventory = []
    skipped_dirs = {"__pycache__", ".git", ".ipynb_checkpoints", "node_modules"}
    
    for fp in all_files:
        if any(s in str(fp) for s in skipped_dirs):
            continue
        info = inventory_file(fp)
        inventory.append(info)
        
        status = "OK"
        if "error" in str(info.get("analysis", {})):
            status = "ERR"
        elif info.get("analysis", {}).get("error"):
            status = "ERR"
        
        print(f"  [{status}] {info['relative_path']} ({info['file_size_hr']})")
    
    print()
    print("=" * 80)
    print("CATEGORIZING DATASETS")
    print("=" * 80)
    
    # Group by source
    sources = defaultdict(list)
    for item in inventory:
        src = item["dataset_name"]
        sources[src].append(item)
    
    source_summary = {}
    for src, items in sorted(sources.items()):
        total_size = sum(i["file_size_bytes"] for i in items)
        formats = set(i["file_format"] for i in items)
        source_summary[src] = {
            "file_count": len(items),
            "total_size_hr": format_bytes(total_size),
            "formats": list(formats),
            "files": [i["relative_path"] for i in items],
        }
        print(f"\n  {src}/ ({len(items)} files, {format_bytes(total_size)})")
        for f in sorted(items, key=lambda x: x["file_size_bytes"], reverse=True):
            print(f"    {f['relative_path']} ({f['file_size_hr']})")
    
    # Generate report
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "datasets_directory": str(DATASETS_DIR),
        "total_files": len(inventory),
        "total_size_bytes": sum(i["file_size_bytes"] for i in inventory),
        "total_size_hr": format_bytes(sum(i["file_size_bytes"] for i in inventory)),
        "sources": source_summary,
        "files": inventory,
    }
    
    report_path = OUTPUT_DIR / "dataset_inventory.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\nInventory report saved: {report_path}")
    print(f"Total: {len(inventory)} files, {format_bytes(sum(i['file_size_bytes'] for i in inventory))}")
    
    # Generate markdown summary
    md_path = OUTPUT_DIR / "DATASET_INVENTORY_REPORT.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Dataset Inventory Report\n\n")
        f.write(f"**Generated:** {report['generated_at']}\n")
        f.write(f"**Directory:** `{DATASETS_DIR}`\n")
        f.write(f"**Total Files:** {report['total_files']}\n")
        f.write(f"**Total Size:** {report['total_size_hr']}\n\n")
        
        f.write("## Source Summary\n\n")
        f.write("| Source | Files | Size | Formats |\n")
        f.write("|---|---|---|---|\n")
        for src, s in sorted(source_summary.items()):
            f.write(f"| `{src}/` | {s['file_count']} | {s['total_size_hr']} | {', '.join(s['formats'])} |\n")
        
        f.write("\n## File Details\n\n")
        f.write("| File | Size | Format | Columns | Rows Sampled | Schema |\n")
        f.write("|---|---|---|---|---|---|\n")
        for item in inventory:
            analysis = item.get("analysis", {})
            if isinstance(analysis, dict):
                cols = analysis.get("columns", analysis.get("headers_count", "?"))
                rows = analysis.get("rows_sampled", analysis.get("estimated_rows", "?"))
                schema_info = ""
                if "schema" in analysis:
                    s = analysis["schema"]
                    schema_info = ", ".join([f"{k}: {v['dtype']}" for k, v in list(s.items())[:5]])
                    if len(s) > 5:
                        schema_info += f" ... +{len(s)-5} more"
                f.write(f"| {item['relative_path']} | {item['file_size_hr']} | {item['file_format']} | {cols} | {rows} | {schema_info} |\n")
            else:
                f.write(f"| {item['relative_path']} | {item['file_size_hr']} | {item['file_format']} | ? | ? | ? |\n")
    
    print(f"Markdown report saved: {md_path}")
    print("Done.")


if __name__ == "__main__":
    main()
