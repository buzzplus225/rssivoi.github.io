import requests
from lxml import html
import yaml
from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta
import re
import os

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def extract_text(element, xpath_expr, default=""):
    """Extrait le texte d'un élément via XPath"""
    results = element.xpath(xpath_expr)
    return results[0].strip() if results else default

def extract_attribute(element, xpath_expr, attr, default=""):
    """Extrait un attribut d'un élément via XPath"""
    results = element.xpath(xpath_expr)
    if results:
        # Si c'est une URL relative, la rendre absolue
        value = results[0]
        if attr == "href" and not value.startswith("http"):
            base = config['options']['base_url']
            value = base + value if value.startswith('/') else base + '/' + value
        return value
    return default

def parse_relative_time(time_str):
    """Convertit 'il y a 32 minutes' en datetime"""
    time_str = time_str.lower().strip()
    
    # Patterns pour le français
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
    
    for pattern, unit in patterns:
        match = re.search(pattern, time_str)
        if match:
            value = int(match.group(1))
            now = datetime.now()
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
    
    return datetime.now()  # Fallback

def scrape_articles(config):
    """Scrape les articles selon la configuration XPath"""
    url = config['site']['url']
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
                'url': extract_attribute(post, config['xpath']['url'], 'href'),
                'image': extract_attribute(post, config['xpath']['image'], 'src'),
                'description': extract_text(post, config['xpath']['description']),
                'pub_time': extract_text(post, config['xpath']['pub_time']),
                'views': extract_text(post, config['xpath']['views'], '0'),
                'comments': extract_text(post, config['xpath']['comments'], '0')
            }
            
            # Si titre ou URL vide, on ignore l'article
            if article['title'] and article['url']:
                # Conversion du temps relatif
                if config['options']['time_relative'] and article['pub_time']:
                    article['pub_date'] = parse_relative_time(article['pub_time'])
                else:
                    article['pub_date'] = datetime.now()
                
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
    fg.lastBuildDate(datetime.now())
    
    for article in articles:
        fe = fg.add_entry()
        fe.title(article['title'])
        fe.link(href=article['url'])
        fe.pubDate(article['pub_date'])
        fe.guid(article['url'], permalink=True)
        
        # Construction du contenu enrichi
        content = f"<p>{article['description']}</p>"
        if article['image']:
            content += f'<img src="{article["image"]}" alt="{article["title"]}" /><br/>'
        content += f"<p>👁️ {article['views']} vues | 💬 {article['comments']} commentaires</p>"
        content += f'<p><a href="{article["url"]}">Lire l\'article complet →</a></p>'
        
        fe.description(content)
        fe.content(content, type='html')
    
    fg.rss_file('feed.xml')
    print(f"✅ Flux RSS généré avec {len(articles)} articles")

if __name__ == "__main__":
    config = load_config()
    articles = scrape_articles(config)
    generate_rss(articles, config)