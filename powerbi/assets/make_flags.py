import base64, csv, io, sys, cairosvg
from PIL import Image
FI = sys.argv[1]; OUT = sys.argv[2]
C = [("Argentina","Argentina","ar"),("Australia","Australia","au"),("Bahrain","Bahrain","bh"),("Bangladesh","Bangladesh","bd"),
     ("Brazil","Brazil","br"),("Canada","Canada","ca"),("France","France","fr"),("Germany","Germany","de"),("India","India","in"),
     ("Indonesia","Indonesia","id"),("Ireland","Ireland","ie"),("Italy","Italy","it"),("Malaysia","Malaysia","my"),
     ("Mauritius","Mauritius","mu"),("Mexico","Mexico","mx"),("Myanmar","Myanmar","mm"),("Netherlands","Netherlands","nl"),
     ("New Zealand","New Zealand","nz"),("Oman","Oman","om"),("Pakistan","Pakistan","pk"),("Poland","Poland","pl"),
     ("Romania","Romania","ro"),("Russian Federation","Russia","ru"),("Saudi Arabia","Saudi Arabia","sa"),("Thailand","Thailand","th"),
     ("Türkiye","Turkey","tr"),("USA","United States of America","us"),("Ukraine","Ukraine","ua"),("United Kingdom","United Kingdom","gb"),
     ("Viet Nam","Vietnam","vn")]
rows = []
for country, mapname, iso in C:
    png = cairosvg.svg2png(url=f"{FI}/flags/4x3/{iso}.svg", output_width=48, output_height=36)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    rows.append({"country": country, "map_name": mapname, "iso2": iso.upper(),
                 "flag": "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()})
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["country", "map_name", "iso2", "flag"]); w.writeheader(); w.writerows(rows)
print(len(rows), max(len(r["flag"]) for r in rows))
