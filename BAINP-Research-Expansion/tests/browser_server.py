import sys,tempfile,uuid,time
from pathlib import Path
sys.path.insert(0,str(Path('research-test/apps/neuroaccess/backend').resolve()))
from api import create_app
from accounts import password_hash
from fastapi.staticfiles import StaticFiles
import uvicorn
folder=tempfile.TemporaryDirectory();app=create_app(folder.name)
with app.state.accounts.connect() as c:c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),'test@example.org','Browser test',password_hash('Browser isolated test password!'),'admin','active',time.time()))
app.mount('/',StaticFiles(directory='research-test/apps/neuroaccess/web',html=True))
uvicorn.run(app,host='127.0.0.1',port=8777,log_level='warning')
