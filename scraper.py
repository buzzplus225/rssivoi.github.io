import requests
from lxml import html
import yaml
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta, timezone
import re
import os

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def extract_text(element, xpath_expr, default=""):
    """Extrait le texte d'un élément via XPath et nettoie les espaces blancs complexes"""
    results = element.xpath(xpath_expr)
    if results:
        # Nettoyage des espaces multiples et caractères de contrôle
        text = " ".join(results[0].split())
        return text.strip()
    return default

def extract_attribute(element, xpath_expr, attr, base_url="", default=""):
    """Extrait un attribut d'un élément via XPath et gère les URLs relatives"""
    results = element.xpath(xpath_expr)
    if results:
        value = results[0].strip()
        # Si c'est une URL relative, la rendre absolue
        if attr == "href" and not value.startswith(("http://", "https://")):
            if base_url:
                value = base_url + value if value.startswith('/') else base_url + '/' + value
        return value
    return default

def parse_relative_time(time_str):
    """Convertit 'il y a 32 minutes' en datetime consciente du fuseau horaire (timezone-aware)"""
    time_str = time_str.lower().strip()
    
    patterns = [
        (r'il y a (\d+) minute?', 'minutes'),
        (r'il y a (\d+) heure?', 'hours'),
        (r'il y a (\d+) jour?', 'days'),
        (r'il y a (\d+) semaine?', 'weeks'),
        (r'il y a (\d+) mois?', 'months'),
        (r'(\d+) minute?', 'minutes'),
        (r'(\d+) heure?', 'hours'),
        (r'(\d+) jour?', 'days'),
    ]
    
    now = datetime.now(timezone.utc) # Utilisation d'un datetime "aware" pour éviter les bugs de flux
    
    for pattern, unit in patterns:
        match = re.search(pattern, time_str)
        if match:
            value = int(match.group(1))
            if unit == 'minutes':
                return now - timedelta(minutes=value)
            elif unit == 'hours':
                return now - timedelta(hours=value)
            elif unit == 'days':
                return now - timedelta(days=value)
            elif unit == 'weeks':
                return now - timedelta(weeks=value)
            elif unit == 'months':
                return now - timedelta(days=value * 30)
    
    return now

def scrape_articles(config):
    """Scrape les articles selon la configuration XPath"""
    url = config['site']['url']
    base_url = config['options'].get('base_url', '')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    tree = html.fromstring(response.content)
    posts = tree.xpath(config['xpath']['post_container'])
    
    articles = []
    for post in posts[:config['options']['max_items']]:
        try:
            article = {
                'title': extract_text(post, config['xpath']['title']),
                'url': extract_attribute(post, config['xpath']['url'], 'href', base_url=base_url),
                'image': extract_attribute(post, config['xpath']['image'], 'src', base_url=base_url),
                'description': extract_text(post, config['xpath']['description']),
                'pub_time': extract_text(post, config['xpath']['pub_time']),
                'views': extract_text(post, config['xpath']['views'], '0'),
                'comments': extract_text(post, config['xpath']['comments'], '0')
            }
            
            if article['title'] and article['url']:
                if config['options']['time_relative'] and article['pub_time']:
                    article['pub_date'] = parse_relative_time(article['pub_time'])
                else:
                    article['pub_date'] = datetime.now(timezone.utc)
                
                articles.append(article)
        except Exception as e:
            print(f"Erreur sur un article: {e}")
            continue
    
    return articles

def generate_rss(articles, config):
    """Génère le flux RSS"""
    fg = FeedGenerator()
    fg.title(config['site']['rss_title'])
    fg.link(href=config['site']['url'], rel='alternate')
    fg.link(href=os.environ.get('RSS_URL', 'https://rssivoi.github.io/feed.xml'), rel='self')
    fg.description(config['site']['rss_description'])
    fg.language('fr')
    fg.lastBuildDate(datetime.now(timezone.utc))
    
    for article in articles:
        fe = fg.add_entry()
        fe.title(article['title'])
        fe.link(href=article['url'])
        fe.pubDate(article['pub_date'])
        fe.guid(article['url'], permalink=True)
        
        # Construction du contenu HTML enrichi
        content = f"<p>{article['description']}</p>"
        if article['image']:
            content += f'<p><img src="{article["image"]}" alt="{article["title"]}" style="max-width:100%;" /></p>'
        content += f"<p><small>👁️ {article['views']} vues | 💬 {article['comments']} commentaires</small></p>"
        content += f'<p><a href="{article["url"]}">Lire l\'article complet →</a></p>'
        
        fe.description(content)
        fe.content(content, type='html')
    
    fg.rss_file('feed.xml')
    print(f"✅ Flux RSS généré avec {len(articles)} articles")

if __name__ == "__main__":
    config = load_config()
    articles = scrape_articles(config)
    generate_rss(articles, config)
