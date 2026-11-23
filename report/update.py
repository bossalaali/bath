"""Refresh the report data from a Windsor.ai Instagram pull.

Usage: python3 update.py <windsor_rows.json>
The input is the JSON returned by Windsor get_data (either the raw tool
result text or a list of rows) with these fields: media_shortcode,
media_type, media_caption, media_views, media_reach, media_profile_visits,
media_shares, media_saved.
Writes store.json (product map + per-post metrics) and data.json (what
index.html reads).
"""
import json, re, sys, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
EMO = re.compile('[\U0001F000-\U0001FAFF☀-➿️‍⁦-⁩]')


def load_rows(path):
    raw = json.load(open(path))
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and 'text' in raw[0]:
        raw = json.loads(raw[0]['text'])
    if isinstance(raw, dict):
        raw = raw.get('data', [])
    return raw


def guess_cat(text):
    if 'بوكس' in text or 'هدية' in text: return 'b'
    if 'عطر' in text: return 'p'
    if any(w in text for w in ('شعر', 'كيرلي', 'شامبو', 'بلسم')): return 'c'
    return 's'


def main(path):
    store = json.load(open(os.path.join(HERE, 'store.json')))
    products, posts = store['products'], store['posts']
    for r in load_rows(path):
        sc = r.get('media_shortcode')
        cap = (r.get('media_caption') or '').strip()
        if not sc: continue
        key = posts.get(sc, {}).get('key')
        if not key:
            hits = [k for k, p in products.items() if any(w.lower() in cap.lower() for w in p['kw'])]
            if len(hits) == 1:
                key = hits[0]
            elif len(hits) > 1 or r.get('media_type') in ('REELS', 'VIDEO'):
                key = '_skip'  # reel or post covering several or unknown products
            else:
                title = EMO.sub('', cap.split('\n')[0]).split('|')[0].strip()
                price = re.search(r'السعر[^\d]*([\d.]+)', cap)
                if not title: continue
                key = 'p_' + sc
                products[key] = {'name': title[:40], 'cat': guess_cat(cap),
                                 'price': float(price.group(1)) if price else None, 'kw': [title]}
        posts[sc] = {'key': key, 'views': r.get('media_views'), 'reach': r.get('media_reach'),
                     'visits': r.get('media_profile_visits'), 'shares': r.get('media_shares'),
                     'saves': r.get('media_saved')}
    agg = {}
    for p in posts.values():
        if p['key'] == '_skip' or p['key'] not in products: continue
        a = agg.setdefault(p['key'], dict(views=0, reach=0, visits=0, shares=0, saves=0))
        for f in a: a[f] += int(p.get(f) or 0)
    # link each product to its main post: the feed post (reels have no visits) with most views
    link = {}
    for sc, p in posts.items():
        k = p['key']
        score = (p.get('visits') is not None, p.get('views') or 0)
        if k in agg and (k not in link or score > link[k][0]):
            link[k] = (score, sc)
    out = []
    for k, a in agg.items():
        pr = products[k]
        out.append(dict(name=pr['name'], cat=pr['cat'], price=pr['price'],
                        url='https://www.instagram.com/p/%s/' % link[k][1], **a))
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    json.dump(store, open(os.path.join(HERE, 'store.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump({'updated': now.strftime('%Y-%m-%dT%H:%M'), 'products': out},
              open(os.path.join(HERE, 'data.json'), 'w'), ensure_ascii=False)
    print(len(out), 'products,', len(posts), 'posts')


if __name__ == '__main__':
    main(sys.argv[1])
