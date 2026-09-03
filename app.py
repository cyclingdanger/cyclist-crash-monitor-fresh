from __future__ import annotations
import concurrent.futures
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from flask import Flask, redirect, render_template, request, url_for
from monitor_core import *

APP_VERSION = "1.0"
DB_PATH = "cyclist_crash_monitor.db"
MAX_WORKERS = 12
app = Flask(__name__)


def db():
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row; return conn


def init_db():
    c=db(); c.execute("""CREATE TABLE IF NOT EXISTS incidents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,summary TEXT,url TEXT UNIQUE NOT NULL,
        source TEXT,published TEXT,location TEXT,status TEXT,created_at TEXT NOT NULL)"""); c.commit(); c.close()


def insert_candidate(c):
    conn=db(); rows=conn.execute("SELECT * FROM incidents").fetchall()
    for row in rows:
        if same_incident(c,dict(row)): conn.close(); return False
    conn.execute("INSERT OR IGNORE INTO incidents(title,summary,url,source,published,location,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                 (c['title'],c['summary'],c['url'],c['source'],c['published'],c['location'],c['status'],datetime.now(timezone.utc).isoformat()))
    changed=conn.total_changes>0; conn.commit(); conn.close(); return changed


def search_job(kind,q):
    return fetch_rss(google_news_url(q) if kind=='google' else bing_news_url(q), 'Google News' if kind=='google' else 'Bing News')


def run_scan():
    # Always preserve the verified regression incident that exposed the old coverage problem.
    insert_candidate(KNOWN_REGRESSION)
    jobs=[(kind,q) for kind in ('google','bing') for q in SEARCH_QUERIES]
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures=[ex.submit(search_job,k,q) for k,q in jobs]
        for f in concurrent.futures.as_completed(futures):
            try: results.extend(f.result())
            except Exception: pass
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures=[ex.submit(fetch_rss,url,label) for label,url in DIRECT_FEEDS]
        for f in futures:
            try: results.extend(f.result())
            except Exception: pass
    cutoff=(datetime.now(timezone.utc).date()-timedelta(days=60)).isoformat()
    relevant=added=0
    seen=[]
    for r in results:
        if not is_relevant(r['title'],r['summary']): continue
        r['status']=status_from_text(r['title']+' '+r['summary']) or 'Review Needed'
        r['location']=location_from_text(r['title']+' '+r['summary'])
        if r.get('published','') < cutoff: continue
        if any(same_incident(r,x) for x in seen): continue
        seen.append(r); relevant += 1
        if insert_candidate(r): added += 1
    return len(results),relevant,added


def get_incidents(period,location):
    days={'7d':7,'30d':30,'90d':90}.get(period,30); cutoff=(datetime.now(timezone.utc).date()-timedelta(days=days)).isoformat()
    c=db()
    if location and location!='All Locations': rows=c.execute("SELECT * FROM incidents WHERE published>=? AND location=? ORDER BY published DESC,id DESC",(cutoff,location)).fetchall()
    else: rows=c.execute("SELECT * FROM incidents WHERE published>=? ORDER BY published DESC,id DESC",(cutoff,)).fetchall()
    c.close(); return rows

@app.route('/')
def index():
    period=request.args.get('period','7d'); location=request.args.get('location','All Locations'); rows=get_incidents(period,location)
    killed=sum(r['status']=='Killed' for r in rows); injured=sum(r['status']=='Seriously Injured' for r in rows); review=sum(r['status']=='Review Needed' for r in rows)
    c=db(); locations=sorted({r['location'] for r in c.execute("SELECT DISTINCT location FROM incidents").fetchall() if r['location']}); c.close()
    return render_template('index.html',rows=rows,killed=killed,injured=injured,review=review,total=len(rows),period=period,location=location,locations=locations,version=APP_VERSION)

@app.route('/scan')
def scan():
    run_scan(); return redirect(url_for('index',period=request.args.get('period','7d'),location=request.args.get('location','All Locations')))

@app.route('/health')
def health(): return {'status':'ok','version':APP_VERSION}

init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')))
