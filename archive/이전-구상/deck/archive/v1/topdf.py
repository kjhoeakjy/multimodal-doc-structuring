import uno, sys, time, subprocess, os
from com.sun.star.beans import PropertyValue
def P(n,v):
    p=PropertyValue(); p.Name=n; p.Value=v; return p
src=os.path.abspath(sys.argv[1]); dst=os.path.abspath(sys.argv[2])
proc=subprocess.Popen(['soffice','--headless','--invisible','--norestore','--accept=socket,host=localhost,port=2002;urp;'])
ctx=None
for _ in range(60):
    try:
        local=uno.getComponentContext()
        r=local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver',local)
        ctx=r.resolve('uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'); break
    except Exception: time.sleep(0.5)
desk=ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop',ctx)
doc=desk.loadComponentFromURL(uno.systemPathToFileUrl(src),'_blank',0,(P('Hidden',True),))
def fix(shape):
    if shape.supportsService('com.sun.star.drawing.GroupShape'):
        for i in range(shape.getCount()): fix(shape.getByIndex(i))
        return
    try:
        if shape.supportsService('com.sun.star.table.TableShape') or not hasattr(shape,'getText'): return
        en=shape.getText().createEnumeration()
        while en.hasMoreElements():
            par=en.nextElement()
            try: par.ParaIsCharacterDistance=False
            except Exception: pass
    except Exception: pass
pages=doc.getDrawPages()
for i in range(pages.getCount()):
    pg=pages.getByIndex(i)
    for j in range(pg.getCount()): fix(pg.getByIndex(j))
doc.storeToURL(uno.systemPathToFileUrl(dst),(P('FilterName','impress_pdf_Export'),))
doc.close(True)
try: desk.terminate()
except Exception: pass
proc.wait(timeout=30)
