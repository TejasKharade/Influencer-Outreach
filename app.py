import os
import streamlit as st
import outreach as o

o.init()
st.set_page_config(page_title='Influencer Outreach',layout='wide')
st.title('Influencer Outreach Assistant')
st.caption('Local application. Real sends require approval and DRY_RUN=0.')
with st.sidebar:
    st.header('Connections')
    for name in ['META_ACCESS_TOKEN','META_IG_USER_ID','GEMINI_API_KEY','GOOGLE_SHEET_ID','SENDER_EMAIL']:
        st.write(('✅' if os.getenv(name) else '⚪')+' '+name)
    st.write('Dry run:',os.getenv('DRY_RUN','1'))
    st.info('Run `python outreach.py auth` once for Google OAuth. Keep `python outreach.py worker` running for scheduled work.')

with st.expander('Create campaign',expanded=not bool(o.rows('SELECT id FROM campaigns'))):
    with st.form('campaign'):
        brand=st.text_input('Brand name'); offer=st.text_area('Collaboration opportunity')
        niche=st.text_input('Niche'); keywords=st.text_input('Profile keywords, comma separated')
        hashtags=st.text_input('Discovery hashtags, comma separated')
        location=st.text_input('Location filter (optional)')
        a,b=st.columns(2); minimum=a.number_input('Minimum followers',min_value=0,value=1000); maximum=b.number_input('Maximum followers',min_value=1,value=100000)
        sender_name=st.text_input('Sender name'); sender_address=st.text_input('Sender business address/contact')
        opt_out=st.text_input('Opt-out wording',value='If this is not of interest, reply “no thanks” and I will not follow up.')
        daily_limit=st.number_input('Daily send cap',min_value=1,max_value=100,value=10)
        if st.form_submit_button('Create campaign'):
            if not all([brand,offer,niche,hashtags,sender_name,sender_address,opt_out]): st.error('Complete all required fields.')
            else:
                try:
                    o.campaign(dict(brand=brand,offer=offer,niche=niche,keywords=keywords,hashtags=hashtags,location=location,min_followers=minimum,max_followers=maximum,sender_name=sender_name,sender_address=sender_address,opt_out=opt_out,daily_limit=daily_limit))
                    st.rerun()
                except ValueError as e: st.error(str(e))

campaigns=o.rows('SELECT * FROM campaigns ORDER BY id DESC')
if not campaigns: st.stop()
cid=st.selectbox('Campaign', [x['id'] for x in campaigns],format_func=lambda x:next(c['brand']+' #'+str(x) for c in campaigns if c['id']==x))
camp=next(x for x in campaigns if x['id']==cid)
with st.expander('Delete campaign'):
    st.warning('This removes the campaign and all its local leads, drafts, and activity. Emails already sent through Gmail remain in Gmail.')
    with st.form('delete_campaign'):
        confirm_campaign=st.checkbox('Confirm deletion of '+camp['brand']+' #'+str(cid))
        if st.form_submit_button('Delete campaign'):
            if not confirm_campaign: st.error('Check the confirmation box first.')
            else:
                try: o.delete_campaign(cid); st.rerun()
                except ValueError as e: st.error(str(e))
with st.expander('Edit discovery hashtags'):
    with st.form('edit_hashtags'):
        revised_tags=st.text_input('Comma-separated hashtags',value=camp['hashtags'])
        if st.form_submit_button('Save hashtags'):
            try: o.update_campaign_hashtags(cid,revised_tags); st.rerun()
            except ValueError as e: st.error(str(e))
st.subheader('Research and preparation')
c1,c2,c3,c4=st.columns(4)
if c1.button('Discover via Meta (optional)'):
    try: st.success(o.discover(cid))
    except o.MetaReviewRequired as e:
        st.warning(str(e))
        st.link_button('Open Meta App Review guidance','https://developers.facebook.com/docs/resp-plat-initiatives/app-review/introduction')
    except Exception as e: st.error(str(e))
if c2.button('Score unscored leads'):
    try: st.success(f"Scored {o.assess(cid)} leads")
    except Exception as e: st.error(str(e))
if c3.button('Generate initial drafts'):
    try: st.success(f"Generated {o.prepare(cid)} drafts")
    except Exception as e: st.error(str(e))
if c4.button('Sync Google Sheet'):
    try: st.success(f"Synced {o.sync_sheet(cid)} leads")
    except Exception as e: st.error(str(e))

with st.expander('Add a publicly sourced lead'):
    with st.form('manual'):
        st.caption('Research public Instagram profiles using the campaign niche, keywords, location, and follower range. Record only details visible on the public profile or linked business page.')
        username=st.text_input('Instagram username'); name=st.text_input('Name')
        niche=st.text_input('Niche/category'); location=st.text_input('Location (if publicly stated)')
        bio=st.text_area('Public profile summary/bio'); followers=st.number_input('Follower count',min_value=0)
        email=st.text_input('Public business or authorized test email'); source=st.text_input('Contact source URL (optional)',help='Useful for documenting where a public business email came from. Leave blank for an authorized test inbox.')
        if st.form_submit_button('Save lead'):
            if not username: st.error('Instagram username is required.')
            else:
                try: o.upsert_lead(cid,username,name=name,niche=niche or None,location=location or None,email=email or None,contact_source=source or None,bio=bio,followers=followers); st.rerun()
                except Exception as e: st.error(str(e))

leads=o.rows('SELECT * FROM leads WHERE campaign_id=? ORDER BY score DESC',(cid,))
st.subheader(f'Leads ({len(leads)})')
st.dataframe([{k:x[k] for k in ['id','username','profile_url','name','niche','followers','location','email','score','status','classification','next_due_at']} for x in leads],hide_index=True,use_container_width=True)
st.subheader('Approval and sending')
st.write('Initial campaign approved:',bool(camp['approved']))
draft_count=o.rows("SELECT COUNT(*) AS n FROM messages m JOIN leads l ON l.id=m.lead_id WHERE l.campaign_id=? AND m.kind='initial' AND m.state='draft'",(cid,))[0]['n']
if not draft_count: st.caption('Add leads, score them, and generate initial drafts before approval.')
if not camp['approved'] and draft_count and st.button('Approve initial campaign batch'):
    try: o.approve(cid); st.rerun()
    except ValueError as e: st.error(str(e))
c1,c2=st.columns(2)
if c1.button('Process replies now'):
    try: o.poll(cid); st.rerun()
    except Exception as e: st.error(str(e))
if c2.button('Send due messages now'):
    try:
        sent=o.send_due(cid)
        if sent: st.success(f'Sent {sent} messages')
        elif os.getenv('DRY_RUN','1')=='1': st.info('Dry run is on. No real emails were sent.')
        else: st.info('No messages are due now. Check each lead’s next_due_at date for its scheduled follow-up.')
    except Exception as e: st.error(str(e))

for lead in leads:
    with st.expander(f"{lead['username']} | {lead['status']} | score {lead['score']}"):
        st.write('Instagram profile:',lead['profile_url'])
        st.write('Niche/category:',lead['niche'] or '—','Location:',lead['location'] or '—')
        if lead['email'] and lead['email'].strip().casefold()==(os.getenv('SENDER_EMAIL') or '').strip().casefold():
            st.warning('This recipient matches the sender inbox. Re-enter this username in the lead form with a separate authorized test email before sending.')
        st.write(lead['summary'] or 'No AI summary yet')
        st.write('Score reason:',lead['reason'] or '—','Contact source:',lead['contact_source'] or '—')
        for msg in o.rows('SELECT * FROM messages WHERE lead_id=? ORDER BY id',(lead['id'],)):
            st.markdown(f"**{msg['kind']} · {msg['state']}** — {msg['subject']}")
            st.text(msg['body'])
        if lead['classification']:
            st.write('Reply classification:',lead['classification'],'Next action:',lead['next_action'])
            reviewed=st.text_area('AI reply draft (edit and review before send)',lead['reply_draft'] or '',key='draft'+str(lead['id']))
            if lead['reply_draft'] and not lead['suppressed'] and st.button('Approve and send reply',key='reply'+str(lead['id'])):
                try: o.approve_reply(lead['id'],reviewed); st.rerun()
                except Exception as e: st.error(str(e))
        c1,c2=st.columns(2)
        if c1.button('Suppress all future outreach',key='stop'+str(lead['id'])):
            with o.db() as con: con.execute('UPDATE leads SET suppressed=1,next_due_at=NULL WHERE id=?',(lead['id'],))
            st.rerun()
        if c2.button('Mark collaboration confirmed',key='confirmed'+str(lead['id'])):
            with o.db() as con: con.execute("UPDATE leads SET status='Collaboration Confirmed',next_due_at=NULL WHERE id=?",(lead['id'],))
            st.rerun()
        with st.form('delete_lead_'+str(lead['id'])):
            confirm_delete=st.checkbox('Confirm deletion of '+lead['username']+' and its local messages/activity')
            if st.form_submit_button('Delete lead'):
                if not confirm_delete: st.error('Check the confirmation box first.')
                else:
                    try: o.delete_lead(cid,lead['id']); st.rerun()
                    except ValueError as e: st.error(str(e))
st.subheader('Activity')
st.dataframe(o.rows('SELECT * FROM events WHERE lead_id IN (SELECT id FROM leads WHERE campaign_id=?) ORDER BY id DESC LIMIT 100',(cid,)),hide_index=True,use_container_width=True)
