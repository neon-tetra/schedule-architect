import json
import sys

with open("model_dump.json") as f:
    data = json.load(f)

var_lookup = {v["var_index"]: v for v in data["variables"]}

def format_domain(domain_list):
    # domain is flat pairs: [lb1, ub1, lb2, ub2, ...]
    pairs = []
    for i in range(0, len(domain_list), 2):
        lb = domain_list[i]
        ub = domain_list[i+1]
        lb_str = "-inf" if lb == -9223372036854775808 else str(lb)
        ub_str = "+inf" if ub == 9223372036854775807 else str(ub)
        pairs.append(f"[{lb_str}, {ub_str}]")
    return pairs

def enrich_constraint(constraint):
    enriched_vars = []
    for idx, coeff in zip(constraint["linear_vars"], constraint["linear_coeffs"]):
        var_info = var_lookup.get(idx, {"var_index": idx, "var_name": "unknown", "lb": "?", "ub": "?"})
        enriched_vars.append({**var_info, "coeff": coeff})
    return {
        "constraint_index": constraint["constraint_index"],
        "constraint_name": constraint["constraint_name"],
        "constraint_domain": format_domain(constraint["linear_domains"]),
        "vars": enriched_vars
    }

def search(query):
    try:
        query_int = int(query)
        matches = [c for c in data["constraints"] if query_int in c["linear_vars"]]
    except ValueError:
        matching_indices = {v["var_index"] for v in data["variables"] if query in v["var_name"]}
        matches = [c for c in data["constraints"] if any(v in c["linear_vars"] for v in matching_indices)]
    
    for m in matches:
        print(json.dumps(enrich_constraint(m), indent=2))
        print("---")

if __name__ == "__main__":
    search(sys.argv[1])