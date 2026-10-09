"""Keyless server-side snapshots. Failed feeds retain their last successful data."""
import json, pathlib, urllib.request, datetime, concurrent.futures, math
ROOT = pathlib.Path(__file__).resolve().parent / 'data'
ROOT.mkdir(exist_ok=True)
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Personal dashboard)', 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)
def nhl(endpoint, key):
    d = get('https://api-web.nhle.com/v1/' + endpoint)
    if not isinstance(d.get(key), list):
        raise ValueError('Unexpected NHL response')
    return d
def quote(symbol):
    d = get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d')
    m = d['chart']['result'][0]['meta']
    p, previous = m['regularMarketPrice'], m.get('chartPreviousClose', m.get('previousClose'))
    if not previous or not math.isfinite(p):
        raise ValueError('Invalid quote')
    return dict(symbol=symbol, price=p, change=p-previous, changePercent=(p/previous-1)*100,
                currency=m.get('currency','USD'), quoteTime=datetime.datetime.fromtimestamp(m['regularMarketTime'],datetime.timezone.utc).isoformat())
def stocks():
    quotes, errors = [], []
    for symbol in ['NDAQ','SPY','DIS','GOOG']:
        try: quotes.append(quote(symbol))
        except Exception as e: errors.append(f'{symbol}: {e}')
    if not quotes: raise ValueError('; '.join(errors))
    return {'quotes':quotes, 'errors':errors}
def save(name, fn):
    path = ROOT / (name+'.json')
    try:
        data = {'fetchedAt':now(), 'data':fn()}
        print(name+': updated')
    except Exception as e:
        try: data = json.loads(path.read_text())
        except Exception: data = {'data':None, 'fetchedAt':None}
        data.update(error=str(e), attemptedAt=now())
        print(name+': '+str(e))
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data), encoding='utf-8')
    tmp.replace(path)
feeds = {'scores':lambda:nhl('score/now','games'), 'standings':lambda:nhl('standings/now','standings'),
         'schedule':lambda:nhl('club-schedule-season/FLA/now','games'), 'stocks':stocks}
if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda item:save(*item), feeds.items()))
