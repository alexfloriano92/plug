import json
import sqlite3
import re
import os
import datetime

# 1. Read candidates.json
try:
    with open('candidates.json', 'r', encoding='utf-8') as f:
        candidates = json.load(f)
except Exception as e:
    print("Erro ao ler candidates.json:", e)
    candidates = {}

# Flatten the list of leads from all niches
leads = []
for nicho, leads_nicho in candidates.items():
    if isinstance(leads_nicho, list):
        leads.extend(leads_nicho)

if not leads:
    print("Nenhum lead encontrado em candidates.json.")
    exit(0)

print(f"Total de {len(leads)} leads lidos de candidates.json.")

# 2. Upsert into prospector.db
conn = sqlite3.connect('prospector.db')
c = conn.cursor()

# Ensure table exists
c.execute('''
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
  email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
  status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
  contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT, endCliente TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime')))
''')

# Insert or update each lead
for lead in leads:
    nome = lead.get('nome', 'Sem nome')
    slug = re.sub(r'[^a-z0-9]+', '-', nome.lower()).strip('-')
    nicho = lead.get('nicho', 'Desconhecido') # Nicho can be passed or inferred if we want, but it's not in the lead dict.
    cidade = "Pouso Alegre" 
    nota = lead.get('nota', 0.0)
    avaliacoes = lead.get('avaliacoes', 0)
    email = lead.get('email', '')
    whatsapp = lead.get('whatsapp', lead.get('telefone', ''))
    siteAntigo = lead.get('site', '')
    motivo = lead.get('motivo', '')
    status = 'novo'
    
    # We only upsert if it's a NEW lead, we don't want to overwrite status of an existing one.
    c.execute("SELECT status FROM leads WHERE slug=?", (slug,))
    row = c.fetchone()
    if row:
        # Exists, maybe update some basic info but don't overwrite status
        c.execute('''
            UPDATE leads 
            SET nota=?, avaliacoes=?, siteAntigo=?, motivo=?, atualizado=datetime('now','localtime')
            WHERE slug=?
        ''', (nota, avaliacoes, siteAntigo, motivo, slug))
    else:
        c.execute('''
            INSERT INTO leads (slug, nome, nicho, cidade, nota, avaliacoes, email, whatsapp, siteAntigo, motivo, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (slug, nome, nicho, cidade, nota, avaliacoes, email, whatsapp, siteAntigo, motivo, status))

conn.commit()

# 3. Read all leads from DB to regenerate snapshot
c.execute("SELECT * FROM leads")
columns = [desc[0] for desc in c.description]
all_leads = []
for row in c.fetchall():
    lead_dict = dict(zip(columns, row))
    all_leads.append(lead_dict)

# 4. Generate leads.md
md_content = "# Leads Prospectados\\n\\n"
for lead in all_leads:
    md_content += f"## {lead['nome']}\\n"
    md_content += f"- **Nicho:** {lead['nicho']}\\n"
    md_content += f"- **Nota:** {lead['nota']} ({lead['avaliacoes']} avaliações)\\n"
    md_content += f"- **Site Antigo:** {lead['siteAntigo']}\\n"
    md_content += f"- **Motivo de Reprovação (Oportunidade):** {lead['motivo']}\\n"
    md_content += f"- **Email:** {lead['email']}\\n"
    md_content += f"- **WhatsApp:** {lead['whatsapp']}\\n"
    md_content += f"- **Status:** {lead['status']}\\n\\n"

with open('leads.md', 'w', encoding='utf-8') as f:
    f.write(md_content)

print("leads.md gerado com sucesso.")

# 5. Update dashboard.html if template exists
template_path = 'C:\\\\Users\\\\User\\\\.gemini\\\\config\\\\plugins\\\\prospector-de-sites\\\\skills\\\\dashboard-leads\\\\references\\\\dashboard-template.html'
if os.path.exists(template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        template_html = f.read()
    
    snapshot_data = {
        "atualizado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "leads": all_leads
    }
    snapshot_json = json.dumps(snapshot_data, ensure_ascii=False)
    
    dashboard_html = template_html.replace('__DADOS__', snapshot_json)
    
    with open('dashboard.html', 'w', encoding='utf-8') as f:
        f.write(dashboard_html)
    print("dashboard.html atualizado com sucesso a partir do template.")
else:
    print(f"Template do dashboard não encontrado em {template_path}")

conn.close()
