"""Build both experiences into the three existing host assets. Python standard library only."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def scope_css(css, scope):
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
    output=[];pos=0
    while pos<len(css):
        start=css.find('{',pos)
        if start<0:break
        prelude=css[pos:start].strip();level=1;end=start+1
        while end<len(css) and level:
            if css[end]=='{':level+=1
            elif css[end]=='}':level-=1
            end+=1
        if level:raise ValueError('Unbalanced CSS')
        body=css[start+1:end-1]
        if prelude.startswith('@media'):
            output.append(prelude+'{'+scope_css(body,scope)+'}')
        elif prelude.startswith('@'):
            raise ValueError('Unsupported at-rule: '+prelude)
        else:
            selectors=[]
            for selector in prelude.split(','):
                selector=selector.strip()
                if selector.startswith(':root'):selector=scope+selector[5:]
                elif re.match(r'body(?=[.# :>\[]|$)',selector):selector=scope+selector[4:]
                elif re.match(r'\.(?:high-contrast|large-text|reduced-motion|contrast|large|extra_large|reduced)(?=[ .:#>\[]|$)',selector):selector=scope+selector
                else:selector=scope+' '+selector
                selectors.append(selector)
            output.append(','.join(selectors)+'{'+body+'}')
        pos=end
    return '\n'.join(output)

def build():
    participant=(ROOT/'participant/home.js').read_text(encoding='utf-8')
    workspace=(ROOT/'frontend/workspace.js').read_text(encoding='utf-8')
    bundle="'use strict';\nif(new URLSearchParams(location.search).get('experience')==='participant'){\ndocument.body.classList.add('participant-experience');\n"+participant+"\n}else{\ndocument.body.classList.add('workspace-experience');\n"+workspace+"\n}\n"
    (ROOT/'frontend/app.js').write_text(bundle,encoding='utf-8')
    css=scope_css((ROOT/'frontend/workspace.css').read_text(encoding='utf-8'),'body.workspace-experience')+'\n'+scope_css((ROOT/'participant/home.css').read_text(encoding='utf-8'),'body.participant-experience')
    (ROOT/'frontend/style.css').write_text(css,encoding='utf-8')
if __name__=='__main__':build()
