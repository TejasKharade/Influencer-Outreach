import outreach as o

def test_hashtag_validation_and_meta_token_not_in_url(monkeypatch):
    assert o.parse_hashtags('#fitness, travel')==['fitness','travel']
    import pytest
    with pytest.raises(ValueError): o.parse_hashtags('#fitness #travel')
    monkeypatch.setenv('META_ACCESS_TOKEN','private-test-token')
    monkeypatch.setenv('META_GRAPH_VERSION','v27.0')
    class Response:
        ok=False
        status_code=400
        def json(self): return {'error':{'message':'Invalid hashtag'}}
    def fake_get(url,params,headers,timeout):
        assert 'private-test-token' not in url
        assert 'private-test-token' not in str(params)
        assert headers['Authorization']=='Bearer private-test-token'
        return Response()
    monkeypatch.setattr(o.requests,'get',fake_get)
    with pytest.raises(RuntimeError,match='Invalid hashtag'): o.meta_get('ig_hashtag_search',{'q':'bad','user_id':'1'})

def test_meta_review_error_is_actionable(monkeypatch):
    monkeypatch.setenv('META_ACCESS_TOKEN','private-test-token')
    class Response:
        ok=False
        status_code=400
        def json(self): return {'error':{'message':"To use 'Instagram Public Content Access', your use of this endpoint must be reviewed and approved by Facebook."}}
    monkeypatch.setattr(o.requests,'get',lambda *a,**k:Response())
    import pytest
    with pytest.raises(o.MetaReviewRequired,match='App Review') as exc:
        o.meta_get('ig_hashtag_search',{'q':'fitness','user_id':'1'})
    assert 'private-test-token' not in str(exc.value)

def test_gemini_model_structured_request(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    monkeypatch.setenv('GEMINI_MODEL','gemini-3.8-flash')
    seen={}
    class Response:
        ok=True
        def json(self): return {'candidates':[{'content':{'parts':[{'text':'{"score": 85}'}]}}]}
    def fake_post(url,headers,json,timeout):
        seen.update(url=url,headers=headers,body=json)
        return Response()
    monkeypatch.setattr(o.requests,'post',fake_post)
    result=o.gemini_model('Assess profile',o.schema({'score':{'type':'integer'}}))
    assert result=={'score':85}
    assert seen['headers']['x-goog-api-key']=='test-key'
    assert seen['body']['generationConfig']['responseJsonSchema']['required']==['score']
    assert seen['url']=='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent'

def test_gemini_timeout_is_clear(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    monkeypatch.setenv('GEMINI_MODEL','gemini-3.5-flash-lite')
    def timed_out(*a,**k): raise o.requests.Timeout('private request details')
    monkeypatch.setattr(o.requests,'post',timed_out)
    import pytest
    with pytest.raises(RuntimeError,match='did not respond within two minutes') as exc:
        o.gemini_model('Score this profile',o.schema({'score':{'type':'integer'}}))
    assert 'private request details' not in str(exc.value)

def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(o,'DB',tmp_path/'test.sqlite3')
    o.init()
    return o.campaign(dict(brand='Test Brand',offer='Test offer',niche='fitness',keywords='fitness',hashtags='fitness',location='',min_followers=100,max_followers=10000,sender_name='Test Sender',sender_address='Test address',opt_out='Reply no thanks',daily_limit=5))

def test_dedup_and_approval(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    first=o.upsert_lead(cid,'@creator',email='creator@example.test',contact_source='https://example.test/contact')
    second=o.upsert_lead(cid,'creator',name='Creator')
    assert first==second
    assert len(o.rows('SELECT * FROM leads'))==1
    assert o.rows('SELECT status FROM leads')[0]['status']=='Email Available'
    with o.db() as c:
        c.execute("INSERT INTO messages(lead_id,kind,subject,body,created_at) VALUES(?,?,?,?,?)",(first,'initial','Hello','Body',o.now()))
    calls=[]
    monkeypatch.setattr(o,'gmail_send',lambda *a,**k:calls.append(1))
    assert o.send_due(cid,dry=False)==0
    assert not calls

def test_researched_niche_and_location_survive_scoring_and_sheet_sync(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    lid=o.upsert_lead(cid,'@creator',name='Creator',niche='Fitness coaching',location='Mumbai',followers=12000)
    assert o.rows('SELECT profile_url FROM leads WHERE id=?',(lid,))[0]['profile_url']=='https://www.instagram.com/creator/'
    monkeypatch.setattr(o,'gemini_model',lambda *args:{'niche':'Lifestyle','summary':'Public fitness creator','score':85,'reason':'Relevant niche'})
    assert o.assess(cid)==1
    lead=o.rows('SELECT niche,location,score FROM leads WHERE id=?',(lid,))[0]
    assert (lead['niche'],lead['location'],lead['score'])==('Fitness coaching','Mumbai',85)
    monkeypatch.setenv('GOOGLE_SHEET_ID','test-sheet')
    writes=[]
    def fake_google(method,url,body=None):
        if method=='GET': return {'sheets':[{'properties':{'title':x}} for x in ['Leads','Campaign','Messages','Activity']]}
        writes.append((method,url,body))
        return {}
    monkeypatch.setattr(o,'google',fake_google)
    assert o.sync_sheet(cid)==1
    sheet_rows=next(body['values'] for method,url,body in writes if method=='PUT' and 'Leads!A1:Q2?' in url)
    assert sheet_rows[1][4]=='Fitness coaching'
    assert sheet_rows[1][7]=='Mumbai'

def test_send_once_and_suppress(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    lid=o.upsert_lead(cid,'creator',email='creator@example.test',contact_source='https://example.test/contact')
    with o.db() as c:
        c.execute("INSERT INTO messages(lead_id,kind,subject,body,created_at) VALUES(?,?,?,?,?)",(lid,'initial','Hello','Body',o.now()))
    o.approve(cid)
    calls=[]
    monkeypatch.setattr(o,'gmail_send',lambda *a,**k:(calls.append(1) or {'id':'message-1','threadId':'thread-1'}))
    monkeypatch.setattr(o,'check_reply',lambda lead:None)
    assert o.send_due(cid,dry=False)==1
    assert o.send_due(cid,dry=False)==0
    assert len(calls)==1
    assert o.rows('SELECT status FROM leads WHERE id=?',(lid,))[0]['status']=='Email Sent'
    with o.db() as c: c.execute('UPDATE leads SET suppressed=1,next_due_at=? WHERE id=?',(o.now(),lid))
    assert o.send_due(cid,dry=False)==0

def test_sheet_sync_uses_matching_range(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    monkeypatch.setenv('GOOGLE_SHEET_ID','test-sheet')
    writes=[]
    def fake_google(method,url,body=None):
        if method=='GET': return {'sheets':[{'properties':{'title':x}} for x in ['Leads','Campaign','Messages','Activity']]}
        writes.append((method,url,body))
        return {}
    monkeypatch.setattr(o,'google',fake_google)
    assert o.sync_sheet(cid)==0
    assert writes[0][0]=='POST' and '/values/Leads!A:Q:clear' in writes[0][1]
    lead_write=writes[1]
    assert lead_write[0]=='PUT'
    assert '/values/Leads!A1:Q1?' in lead_write[1]
    assert lead_write[2]['range']=='Leads!A1:Q1'

def test_google_error_shows_message_without_url(monkeypatch):
    monkeypatch.setattr(o,'google_creds',lambda:'private-test-token')
    class Response:
        ok=False
        status_code=400
        def json(self): return {'error':{'message':'Unable to parse range: Leads!A1:Q'}}
    monkeypatch.setattr(o.requests,'request',lambda *a,**k:Response())
    import pytest
    with pytest.raises(RuntimeError,match='Unable to parse range') as exc:
        o.google('PUT','https://sheets.googleapis.com/private-test-sheet/values/Leads!A1:Q')
    assert 'private-test-token' not in str(exc.value)
    assert 'private-test-sheet' not in str(exc.value)

def test_new_initial_draft_requires_fresh_approval(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    import pytest
    with pytest.raises(ValueError,match='Generate and review'):
        o.approve(cid)
    first=o.upsert_lead(cid,'first',email='first@example.test',contact_source='https://example.test/contact')
    with o.db() as c:
        c.execute('UPDATE leads SET score=85,summary=? WHERE id=?',('Relevant profile',first))
    monkeypatch.setattr(o,'gemini_model',lambda *a,**k:{'subject':'Hello','body':'Test body'})
    assert o.prepare(cid)==1
    o.approve(cid)
    assert o.rows('SELECT approved FROM campaigns WHERE id=?',(cid,))[0]['approved']==1
    second=o.upsert_lead(cid,'second',email='second@example.test',contact_source='https://example.test/contact')
    with o.db() as c:
        c.execute('UPDATE leads SET score=80,summary=? WHERE id=?',('Another profile',second))
    assert o.prepare(cid)==1
    assert o.rows('SELECT approved FROM campaigns WHERE id=?',(cid,))[0]['approved']==0

def test_optional_contact_source_and_separate_recipient(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    monkeypatch.setenv('SENDER_EMAIL','sender@example.test')
    import pytest
    with pytest.raises(ValueError,match='HTTPS'):
        o.upsert_lead(cid,'creator',email='recipient@example.test',contact_source='-')
    assert o.upsert_lead(cid,'creator',email='recipient@example.test')
    with pytest.raises(ValueError,match='separate authorized recipient'):
        o.upsert_lead(cid,'creator',email='sender@example.test',contact_source='https://example.test/profile')

def test_delete_lead_removes_related_local_records(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    lid=o.upsert_lead(cid,'creator',email='creator@example.test',contact_source='https://example.test/profile')
    with o.db() as c:
        c.execute("INSERT INTO messages(lead_id,kind,subject,body,created_at) VALUES(?,?,?,?,?)",(lid,'initial','Hello','Body',o.now()))
        o.event(c,lid,'added')
        c.execute('INSERT INTO seen_gmail(id,lead_id) VALUES(?,?)',('gmail-1',lid))
    o.delete_lead(cid,lid)
    for table in ('leads','messages','events','seen_gmail'):
        assert not o.rows('SELECT * FROM '+table)

def test_delete_campaign_removes_related_local_records(tmp_path,monkeypatch):
    cid=setup_db(tmp_path,monkeypatch)
    lid=o.upsert_lead(cid,'creator',email='creator@example.test',contact_source='https://example.test/profile')
    with o.db() as c:
        c.execute("INSERT INTO messages(lead_id,kind,subject,body,created_at) VALUES(?,?,?,?,?)",(lid,'initial','Hello','Body',o.now()))
        o.event(c,lid,'added')
        c.execute('INSERT INTO seen_gmail(id,lead_id) VALUES(?,?)',('gmail-1',lid))
    o.delete_campaign(cid)
    for table in ('campaigns','leads','messages','events','seen_gmail'):
        assert not o.rows('SELECT * FROM '+table)
