import duckdb, json, os, subprocess, sys, time, zipfile

ZIP = os.environ.get("DATATHON_ZIP", "data/synthetic_microdata_2021-2024_20260921.zip")
ROOT = "synthetic_microdata_2021-2024_20260921"
TMP = "data/tmp_csv"
PQ = "data/pq"
os.makedirs(PQ, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

forms = sys.argv[1:]
z = zipfile.ZipFile(ZIP)
man = json.loads(z.read(f"{ROOT}/MANIFEST.json"))
con = duckdb.connect()
con.execute("PRAGMA memory_limit='1800MB'")
os.makedirs('data/tmp_duck', exist_ok=True)
con.execute("PRAGMA temp_directory='data/tmp_duck'")

log = []
for r in man:
    if forms and r["form"] not in forms:
        continue
    key = r['path'].replace('/', '__').rsplit('.', 1)[0]
    out = f"{PQ}/{key}.parquet"
    if os.path.exists(out):
        continue
    t0 = time.time()
    subprocess.run(["unzip", "-q", "-o", ZIP, f"{ROOT}/{r['path']}", "-d", TMP], check=True)
    src = f"{TMP}/{ROOT}/{r['path']}"
    opts = "quote='\"', ignore_errors=false, sample_size=-1"
    try:
        con.execute(f"copy (select * from read_csv_auto('{src}', {opts})) to '{out}' (format parquet, compression zstd)")
    except Exception as e:
        con.execute(f"copy (select * from read_csv_auto('{src}', {opts}, all_varchar=true)) to '{out}' (format parquet, compression zstd)")
        log.append((r["path"], "fallback all_varchar", str(e)[:80]))
    os.remove(src)
    print(f"{key:44} {r['rows_synthetic']:>10,} rows  "
          f"{os.path.getsize(out)/1e6:7.1f} MB  {time.time()-t0:5.1f}s", flush=True)

for l in log:
    print("NOTE", l)
