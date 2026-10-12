"""Monta prancheta_cartola.html a partir de app_template.html + engine.js + model_data.json."""
import re
t=open('app_template.html',encoding='utf-8').read(); s=open('engine.js',encoding='utf-8').read()
eng=re.sub(r"if\(typeof module!=='undefined'\)[^\n]*\n?","",s)
data=open('model_data.json',encoding='utf-8').read().replace('</','<\\/')
open('prancheta_cartola.html','w',encoding='utf-8').write(t.replace('__DATA__',data).replace('__ENGINE__',eng))
print('prancheta_cartola.html gerado')
