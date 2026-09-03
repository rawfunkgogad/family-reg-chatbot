import json
from pathlib import Path

corpus_dir = Path(__file__).resolve().parent.parent / "data" / "corpus"
f_dirs = corpus_dir / "scourt_family_directives_precedents.json"
f_easylaw = corpus_dir / "easylaw_family_reg_corpus.json"
f_efamily = corpus_dir / "efamily_scourt_guide_corpus.json"
f_master = corpus_dir / "master_family_reg_knowledge_corpus.json"
f_integrated = corpus_dir / "integrated_family_reg_tdm_corpus.json"

docs_dirs = json.load(open(f_dirs, encoding="utf-8"))
docs_easylaw = json.load(open(f_easylaw, encoding="utf-8"))
docs_efamily = json.load(open(f_efamily, encoding="utf-8"))

# 1. 포털 2종 통합 (190건)
integrated = docs_efamily + docs_easylaw
with open(f_integrated, "w", encoding="utf-8") as f:
    json.dump(integrated, f, ensure_ascii=False, indent=2)

# 2. 마스터 전체 통합 (468건)
master = docs_dirs + docs_efamily + docs_easylaw
print(f"Combined: {len(docs_dirs)} (대법원 예규/선례) + {len(docs_efamily)} (전자가족관계) + {len(docs_easylaw)} (생활법령) = {len(master)} docs")

ids = set()
for d in master:
    doc_id = d["id"]
    if doc_id in ids:
        raise ValueError(f"Duplicate ID found: {doc_id}")
    ids.add(doc_id)

with open(f_master, "w", encoding="utf-8") as f:
    json.dump(master, f, ensure_ascii=False, indent=2)

print(f"Master corpus created successfully at {f_master} ({f_master.stat().st_size/1024:.1f} KB)")
