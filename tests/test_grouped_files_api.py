import urllib.request
import json

def test_grouped_files():
    print("Testing GET /api/admin/files ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/admin/files") as res:
        data = json.loads(res.read().decode('utf-8'))
        print(f"-> Total Files: {data.get('total_files')}, Total Chunks: {data.get('total_chunks')}")
        assert data.get("total_files", 0) > 0
        assert data.get("total_chunks", 0) > 0
        
        for idx, file_info in enumerate(data.get("files", []), 1):
            print(f"  [{idx}] {file_info['file_name']} ({file_info['file_type']}) - {file_info['chunks_count']}개 청크 (약 {file_info['total_chars']/1024:.1f} KB)")
            assert len(file_info["chunks"]) == file_info["chunks_count"]

    print("\nGrouped Files API verified successfully!")

if __name__ == "__main__":
    test_grouped_files()
