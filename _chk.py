import sys
sys.path.insert(0,"/repo/backend")
from app.painting.services.importing import import_guide_html, make_db_resolver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.painting.models import Paint
db=sessionmaker(bind=create_engine("sqlite:////data/stl_inventory.db"))()
r=make_db_resolver(db)
def info(pid):
    p=db.get(Paint,pid); return f"{p.name} / {p.code}" if p else None
for nm,br in [("Titanium White 001","Expert Acrylics"),("Bold Titanium White 001","Pro Acryl"),("Titanium White 001","Pro Acryl")]:
    pid=r(nm,br); print(f"{nm!r:34} [{br:16}] -> {info(pid) if pid else 'UNRESOLVED'}")
html=open("/repo/geralt.html",encoding="utf-8").read()
_,rep=import_guide_html(html, slug="g", resolve_paint=r)
print("Geralt RESOLVED",rep.resolved_paints,"UNRESOLVED",len(rep.unresolved_paints))
for u in rep.unresolved_paints: print("  -",u["name"],"|",u["brand"])
