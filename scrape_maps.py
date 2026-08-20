"""
Prospector - Google Maps Scraper
Busca negócios nos nichos configurados, filtra por nota/avaliações/site,
avalia qualidade do site e coleta e-mail/WhatsApp.
"""
import json
import time
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

# --- CONFIG ---
CONFIG_PATH = r"c:\Users\User\Documents\Clientes-plug\clientes\prospector-config.json"
OUTPUT_PATH = r"c:\Users\User\Documents\Clientes-plug\clientes\candidates.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

cidade = config["prospeccao"]["cidade"]
nichos = config["prospeccao"]["nichos"]
leads_por_busca = 3

# Run only 1 niche at a time for reliability
NICHO_ATUAL = "clínica médica"
search_queries = [f"{NICHO_ATUAL} em {cidade}"]

MIN_RATING = 4.7
MIN_REVIEWS = 40
SOCIAL_DOMAINS = [
    "instagram.com", "facebook.com", "linktr.ee", "linktree.com",
    "dietbox.me", "bio.site", "doctoralia.com", "localtreino.com",
    "acheioprofissional.com", "google.com/site", "sites.google.com"
]

def extract_rating_reviews(page):
    """Extract rating and review count from a Google Maps place panel."""
    rating = 0.0
    reviews = 0
    
    # Method 1: Look for the F7nice container (rating + reviews)
    try:
        f7 = page.locator("div.F7nice").first
        if f7.count() > 0:
            # Get the full text content: usually "4,9(123)" or "4,9 (123)" or "5,0\n(80)"
            full_text = f7.inner_text().replace('\n', ' ').strip()
            
            # Try pattern: "4,9 (80)" or "4,9(80)" (Portuguese format)
            m = re.search(r'(\d[,\.]\d)\s*\((\d+)\)', full_text)
            if m:
                rating = float(m.group(1).replace(",", "."))
                reviews = int(m.group(2).replace(".", ""))
            else:
                # Try to find just the rating
                m2 = re.search(r'(\d[,\.]\d)', full_text)
                if m2:
                    rating = float(m2.group(1).replace(",", "."))
                # Try to find just the review count
                m3 = re.search(r'\((\d+)\)', full_text)
                if m3:
                    reviews = int(m3.group(1).replace(".", ""))
    except Exception as e:
        pass
    
    # Method 2: Try aria-label on the rating element
    if reviews == 0:
        try:
            stars_elem = page.locator("span[role='img'][aria-label*='estrela']").first
            if stars_elem.count() > 0:
                label = stars_elem.get_attribute("aria-label")
                if label:
                    m = re.search(r'(\d[,\.]\d)', label)
                    if m:
                        rating = float(m.group(1).replace(",", "."))
        except:
            pass
        
        try:
            # Try to find review count from the button/link text
            review_elem = page.locator("button[jsaction*='review'], a[href*='review']").first
            if review_elem.count() > 0:
                text = review_elem.inner_text()
                m = re.search(r'(\d+)', text)
                if m:
                    reviews = int(m.group(1))
        except:
            pass
    
    # Method 3: Search all text spans for patterns like "4,9 estrelas" and "123 avaliações"
    if reviews == 0:
        try:
            all_text = page.locator("[class*='fontBody']").all_inner_texts()
            for t in all_text:
                if reviews == 0:
                    m = re.search(r'(\d+)\s*avalia', t)
                    if m:
                        reviews = int(m.group(1))
        except:
            pass
    
    return rating, reviews


def extract_phone(page):
    """Extract phone number from place panel."""
    phone = ""
    try:
        # Method 1: Copy phone button
        selectors = [
            "button[data-tooltip*='telefone']",
            "button[aria-label*='Telefone']",
            "button[aria-label*='telefone']",
            "a[href^='tel:']"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if btn.count() > 0:
                aria = btn.get_attribute("aria-label") or ""
                if ":" in aria:
                    phone = aria.split(":", 1)[-1].strip()
                    break
                href = btn.get_attribute("href") or ""
                if href.startswith("tel:"):
                    phone = href[4:].strip()
                    break
    except:
        pass
    return phone


def extract_website(page):
    """Extract website URL from place panel."""
    website = ""
    try:
        selectors = [
            "a[data-tooltip*='website']",
            "a[data-tooltip*='Website']",
            "a[aria-label*='website']",
            "a[aria-label*='Website']",
            "a[data-item-id='authority']"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if btn.count() > 0:
                website = btn.get_attribute("href") or ""
                if website:
                    break
    except:
        pass
    return website


def extract_address(page):
    """Extract address from place panel."""
    address = ""
    try:
        selectors = [
            "button[data-tooltip*='endereço']",
            "button[data-tooltip*='Endereço']",
            "button[aria-label*='Endereço']",
            "button[aria-label*='endereço']",
            "button[data-item-id='address']"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if btn.count() > 0:
                aria = btn.get_attribute("aria-label") or ""
                if ":" in aria:
                    address = aria.split(":", 1)[-1].strip()
                    break
                text = btn.inner_text()
                if text:
                    address = text.strip()
                    break
    except:
        pass
    return address


def extract_whatsapp_from_site(page, site_url):
    """Visit the lead's website and try to find email and WhatsApp."""
    email = ""
    whatsapp = ""
    motivo_site_ruim = []
    
    try:
        site_page = page.context.new_page()
        site_page.goto(site_url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(3)
        
        html = site_page.content().lower()
        
        # --- Find email ---
        emails_found = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html)
        # Filter out common fake/template emails
        for e in emails_found:
            if e and not any(x in e for x in ['example', 'teste', 'sentry', 'wix', 'sentry', '@sentry']):
                email = e
                break
        
        # Also check for mailto: links
        if not email:
            mailto = re.findall(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html)
            if mailto:
                email = mailto[0]
        
        # --- Find WhatsApp ---
        wa_patterns = [
            r'wa\.me/(\d+)',
            r'api\.whatsapp\.com/send\?phone=(\d+)',
            r'whatsapp\.com/send\?phone=(\d+)',
        ]
        for pat in wa_patterns:
            m = re.search(pat, html)
            if m:
                whatsapp = m.group(1)
                break
        
        # --- Evaluate site quality ---
        # Check for platform indicators (bad)
        if 'wix.com' in html or 'wixsite.com' in site_url.lower():
            motivo_site_ruim.append("hospedado no Wix gratuito")
        if 'sites.google.com' in site_url.lower() or 'google.com/site' in site_url.lower():
            motivo_site_ruim.append("hospedado no Google Sites")
        if 'wordpress.com' in site_url.lower() and '.wordpress.com' in site_url.lower():
            motivo_site_ruim.append("subdomínio WordPress.com gratuito")
        
        # Check for responsive meta tag
        if '<meta name="viewport"' not in html:
            motivo_site_ruim.append("sem meta viewport (não responsivo)")
        
        # Check for CTA (WhatsApp button, agendamento, etc.)
        has_cta = any(x in html for x in ['wa.me', 'whatsapp', 'agendar', 'agendamento', 'marcar consulta', 'fale conosco', 'entre em contato'])
        if not has_cta:
            motivo_site_ruim.append("sem CTA de contato/agendamento")
        
        # Check for social proof
        has_social_proof = any(x in html for x in ['depoimento', 'avaliação', 'avaliacao', 'testemunho', 'pacientes dizem', 'clientes dizem'])
        if not has_social_proof:
            motivo_site_ruim.append("sem prova social/depoimentos")
        
        # Check for old/basic design indicators
        title = site_page.title()
        
        site_page.close()
        
    except Exception as e:
        motivo_site_ruim.append(f"site com erro ao carregar: {str(e)[:50]}")
        try:
            site_page.close()
        except:
            pass
    
    motivo = "; ".join(motivo_site_ruim) if motivo_site_ruim else ""
    return email, whatsapp, motivo


def run():
    """Main scraper function."""
    # Load existing candidates to avoid duplicates
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except:
        existing = {}
    
    all_results = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="pt-BR",
            viewport={"width": 1280, "height": 720}
        )
        
        for query in search_queries:
            nicho_key = query.split(" em ")[0]
            print(f"\n{'='*50}")
            print(f"  BUSCANDO: {query}")
            print(f"{'='*50}")
            
            page = context.new_page()
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            print(f"  URL: {search_url}")
            page.goto(search_url)
            time.sleep(4)
            
            # Accept cookies if prompted
            try:
                accept_btn = page.locator("button:has-text('Aceitar'), button:has-text('Accept')")
                if accept_btn.count() > 0:
                    accept_btn.first.click()
                    time.sleep(1)
            except:
                pass
            
            # Wait for results
            try:
                page.wait_for_selector("a[href*='/maps/place/']", timeout=15000)
                print("  ✓ Resultados carregados")
            except:
                print("  ✗ Sem resultados encontrados")
                page.close()
                all_results[nicho_key] = []
                continue
            
            # Scroll the feed to load more results
            try:
                feed = page.locator("div[role='feed']")
                if feed.count() > 0:
                    print("  Scrollando feed...")
                    for _ in range(10):
                        feed.evaluate("el => el.scrollTop = el.scrollHeight")
                        time.sleep(1.5)
            except:
                print("  Feed não encontrado, continuando...")
            
            # Collect all place links
            place_links = page.locator("a[href*='/maps/place/']")
            total = place_links.count()
            print(f"  Encontrados {total} negócios")
            
            qualified = []
            discarded = []
            
            limit = min(25, total)
            for i in range(limit):
                if len(qualified) >= 3:
                    print("\n  Encontrados 3 qualificados. Parando a busca.")
                    break
                try:
                    # Re-query in case DOM changed
                    place_links = page.locator("a[href*='/maps/place/']")
                    if i >= place_links.count():
                        break
                    
                    href = place_links.nth(i).get_attribute("href")
                    place_links.nth(i).click()
                    time.sleep(2.5)
                    
                    # Extract name
                    name_elem = page.locator("h1.DUwDvf, h1[class*='header']").first
                    name = name_elem.inner_text() if name_elem.count() > 0 else f"Negócio #{i+1}"
                    
                    # Extract rating and reviews
                    rating, reviews = extract_rating_reviews(page)
                    
                    # Extract phone
                    phone = extract_phone(page)
                    
                    # Extract website
                    website = extract_website(page)
                    
                    # Extract address
                    address = extract_address(page)
                    
                    print(f"\n  [{i+1}/{limit}] {name}")
                    print(f"      Nota: {rating} | Avaliações: {reviews} | Site: {website[:50] if website else 'N/A'}")
                    
                    # --- FILTRO 1: Potencial financeiro ---
                    # if rating < MIN_RATING or reviews < MIN_REVIEWS:
                    #     reason = f"nota {rating}, {reviews} avaliações (mín: {MIN_RATING}/{MIN_REVIEWS})"
                    #     print(f"      ✗ REPROVADO (Filtro 1 - potencial): {reason}")
                    #     discarded.append({"nome": name, "motivo": reason})
                    #     continue
                    
                    # --- FILTRO 2: Tem site próprio ---
                    if not website:
                        print(f"      ✗ REPROVADO (Filtro 2 - sem site)")
                        discarded.append({"nome": name, "motivo": "sem site"})
                        continue
                    
                    is_social = any(domain in website.lower() for domain in SOCIAL_DOMAINS)
                    if is_social:
                        print(f"      ✗ REPROVADO (Filtro 2 - site de terceiro: {website})")
                        discarded.append({"nome": name, "motivo": f"site de terceiro: {website}"})
                        continue
                    
                    print(f"      ✓ Passou filtros 1 e 2! Avaliando site...")
                    
                    # --- FILTRO 3: Avaliar site + coletar email/whatsapp ---
                    email, whatsapp, motivo = extract_whatsapp_from_site(page, website)
                    
                    # Infer whatsapp from phone if not found on site
                    if not whatsapp and phone:
                        clean_phone = re.sub(r'[^\d]', '', phone)
                        # Brazilian mobile numbers have 9th digit
                        if len(clean_phone) >= 10:
                            if len(clean_phone) == 10 and clean_phone[2] == '9':
                                whatsapp = f"55{clean_phone}"
                            elif len(clean_phone) == 11 and clean_phone[2] == '9':
                                whatsapp = f"55{clean_phone}"
                            elif len(clean_phone) >= 12 and clean_phone.startswith('55'):
                                whatsapp = clean_phone
                    
                    if not email:
                        print(f"      ✗ DESCARTADO (sem e-mail público)")
                        discarded.append({
                            "nome": name, "nota": rating, "avaliacoes": reviews,
                            "telefone": phone, "whatsapp": whatsapp,
                            "site": website, "motivo": "sem e-mail público encontrado"
                        })
                        continue
                    
                    if not motivo:
                        # Site seems decent - check if it's on a free platform at least
                        motivo = "site funcional mas passível de melhoria"
                    
                    print(f"      ★ QUALIFICADO!")
                    print(f"        E-mail: {email}")
                    print(f"        WhatsApp: {whatsapp or 'N/A'}")
                    print(f"        Motivo: {motivo}")
                    
                    qualified.append({
                        "nome": name,
                        "nota": rating,
                        "avaliacoes": reviews,
                        "site": website,
                        "telefone": phone,
                        "whatsapp": whatsapp,
                        "email": email,
                        "endereco": address,
                        "maps_url": href,
                        "motivo": motivo
                    })
                    
                    if len(qualified) >= leads_por_busca:
                        print(f"\n  Meta de {leads_por_busca} leads atingida para {nicho_key}!")
                        break
                        
                except Exception as e:
                    print(f"      ERRO ao analisar item {i}: {e}")
                    continue
            
            all_results[nicho_key] = qualified
            print(f"\n  Resumo {nicho_key}: {len(qualified)} qualificados, {len(discarded)} descartados")
            page.close()
        
        browser.close()
    
    # Merge with existing results (don't overwrite previous leads)
    for k, v in all_results.items():
        if k not in existing:
            existing[k] = v
        else:
            existing_names = {lead["nome"] for lead in existing[k]}
            for lead in v:
                if lead["nome"] not in existing_names:
                    existing[k].append(lead)
    
    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"  RESULTADOS SALVOS em: {OUTPUT_PATH}")
    print(f"{'='*50}")
    total_leads = 0
    for k, v in existing.items():
        count = len(v)
        total_leads += count
        print(f"  {k}: {count} leads")
    print(f"  TOTAL: {total_leads} leads")


if __name__ == "__main__":
    run()
