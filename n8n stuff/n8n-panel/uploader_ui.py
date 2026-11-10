"""HTML/JS for the Uploader tab. app.py injects these into PAGE (see inject())."""

TAB_BUTTON = '<button type="button" data-tab="uploader">Uploader</button>\r\n'

SECTION = r"""<section id="view-uploader" hidden>
<p class="meta" style="margin:0 0 8px">Ρίξε βίντεο στον φάκελο inbox του καναλιού. Εδώ βλέπεις προτάσεις τίτλου, περιγραφής, tags και playlist, τα διορθώνεις και πατάς Έγκριση. Το upload γίνεται σε private με προγραμματισμένη ώρα δημοσίευσης στο επόμενο ελεύθερο slot.</p>
<p class="meta" id="up-info" style="margin:0 0 8px"></p>
<div class="toolbar">
<button class="g" id="up-scan" type="button">Σάρωση inbox</button>
<button class="g" id="up-suggest-all" type="button">Προτάσεις για όλα τα νέα</button>
<button class="g" id="up-reslot" type="button">Ξαναμοίρασμα ημερομηνιών</button>
<button class="g" id="up-settings-btn" type="button">Πρόγραμμα καναλιού</button>
</div>
<div id="up-settings" hidden style="margin:10px 0;padding:10px;border:1px solid var(--bd);border-radius:12px"></div>
<div id="up-list" style="margin-top:12px;display:grid;gap:10px"></div>
</section>
"""

JS = r"""
/* ---------------- Uploader tab ---------------- */
let upChannel = '', upData = null, upTimer = null, upDirty = false;
const UP_DAYS = ['Δευ','Τρί','Τετ','Πέμ','Παρ','Σάβ','Κυρ'];
const UP_STATUS = {new:'Νέο', ready:'Έτοιμο για έλεγχο', approved:'Σε ουρά upload', uploading:'Ανεβαίνει…', done:'Ανέβηκε', error:'Σφάλμα'};
function upLocal(iso){
  if (!iso) return '';
  const d = new Date(iso); if (isNaN(d)) return '';
  const p = n => String(n).padStart(2,'0');
  return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+'T'+p(d.getHours())+':'+p(d.getMinutes());
}
function upIso(local){
  if (!local) return '';
  const d = new Date(local); if (isNaN(d)) return '';
  return d.toISOString().slice(0,19)+'Z';
}
async function loadUploader(){
  if (!upChannel && channels.length) upChannel = channels[0].id;
  if (!upChannel) return;
  try{
    upData = await api('/api/uploader?channel=' + encodeURIComponent(upChannel));
    drawUploader();
  }catch(e){ $('up-list').innerHTML = '<p class="meta">'+escapeHtml(e.message)+'</p>'; }
  clearTimeout(upTimer);
  upTimer = setTimeout(() => { if (tab === 'uploader' && !upDirty) loadUploader(); }, 6000);
}
function drawUpSettings(){
  const s = upData.settings, box = $('up-settings');
  box.innerHTML = '<div class="meta">Σε ποιες μέρες/ώρα δημοσιεύονται τα νέα βίντεο (ώρα Ελλάδας). Παραλείπονται slots που είναι ήδη πιασμένα στο κανάλι ή στην ουρά.</div>'
    + '<div class="chips" style="margin:8px 0">' + UP_DAYS.map((n,i)=>'<label class="chip'+(s.weekdays.includes(i)?' on':'')+'" style="cursor:pointer"><input type="checkbox" data-wd="'+i+'" '+(s.weekdays.includes(i)?'checked':'')+' hidden>'+n+'</label>').join('') + '</div>'
    + '<label class="meta">Ώρα <input id="up-hour" type="number" min="0" max="23" value="'+s.hour+'" style="width:70px"></label> '
    + '<label class="meta">Κατηγορία id <input id="up-cat" value="'+escapeHtml(s.category)+'" style="width:60px"></label> '
    + '<label class="meta"><input id="up-kids" type="checkbox" '+(s.made_for_kids?'checked':'')+'> Για παιδιά</label>'
    + '<div style="margin-top:8px"><div class="meta">Υπόδειξη στυλ για το AI</div><input id="up-hint" style="width:100%" value="'+escapeHtml(s.style_hint)+'"></div>'
    + '<div style="margin-top:8px"><div class="meta">Default tags (με κόμμα)</div><input id="up-dtags" style="width:100%" value="'+escapeHtml(s.default_tags)+'"></div>'
    + '<div style="margin-top:8px"><div class="meta">Footer περιγραφής (links κλπ.) — μπαίνει σε κάθε περιγραφή</div><textarea id="up-footer" rows="4" style="width:100%">'+escapeHtml(s.desc_footer)+'</textarea></div>'
    + '<div style="margin-top:8px"><button type="button" id="up-save-settings">Αποθήκευση προγράμματος</button></div>';
  box.querySelectorAll('[data-wd]').forEach(cb => cb.onchange = () => cb.parentElement.classList.toggle('on', cb.checked));
  $('up-save-settings').onclick = async () => {
    const wd = [...box.querySelectorAll('[data-wd]')].filter(c=>c.checked).map(c=>Number(c.dataset.wd));
    try{
      await api('/api/uploader/settings', {method:'POST', body: JSON.stringify({channel: upChannel, weekdays: wd, hour: Number($('up-hour').value), category: $('up-cat').value, made_for_kids: $('up-kids').checked, style_hint: $('up-hint').value, default_tags: $('up-dtags').value, desc_footer: $('up-footer').value})});
      $('up-settings').hidden = true; loadUploader();
    }catch(e){ alert(e.message); }
  };
}
function upCard(it){
  const locked = ['approved','uploading','done'].includes(it.status);
  const dis = locked ? 'disabled' : '';
  const sugg = (it.suggestions||[]).length > 1 && !locked
    ? '<div class="chips" style="margin:4px 0">' + it.suggestions.map((t,i)=>'<button type="button" class="chip" data-pick="'+i+'">'+escapeHtml(t)+'</button>').join('') + '</div>' : '';
  const badge = '<span class="badge '+(it.status==='error'?'bad':it.status==='done'?'ok':'')+'">'+escapeHtml(UP_STATUS[it.status]||it.status)+'</span>';
  const prog = it.status==='uploading' ? '<div class="pbar"><i style="width:'+Math.round((it.progress||0)*100)+'%"></i></div>' : '';
  const link = it.video_id ? ' · <a href="https://studio.youtube.com/video/'+it.video_id+'/edit" target="_blank" rel="noopener">Studio</a>' : '';
  const err = it.error ? '<div class="meta" style="color:#f08a8a">'+escapeHtml(it.error)+'</div>' : '';
  const warn = it.audio ? '<div class="meta" style="color:#f0c36a">Αρχείο ήχου: το YouTube θέλει βίντεο. Φτιάξε πρώτα βίντεο (π.χ. Beat Video Maker).</div>' : '';
  let buttons = '';
  if (it.status === 'new') buttons = '<button type="button" data-act="suggest">Πρότεινε μεταδεδομένα</button><button class="g" type="button" data-act="skip">Παράλειψη</button>';
  else if (it.status === 'ready') buttons = '<button type="button" data-act="approve">Έγκριση &amp; Upload</button><button class="g" type="button" data-act="save">Αποθήκευση</button><button class="g" type="button" data-act="suggest">Νέες προτάσεις</button><button class="g" type="button" data-act="skip">Παράλειψη</button>';
  else if (it.status === 'approved') buttons = '<button class="g" type="button" data-act="unapprove">Ακύρωση</button>';
  else if (it.status === 'error') buttons = '<button type="button" data-act="retry">Ξαναδοκίμασε</button><button class="g" type="button" data-act="skip">Παράλειψη</button>';
  const fields = it.status === 'new' ? '' :
    '<input data-f="title" '+dis+' maxlength="100" placeholder="Τίτλος" style="width:100%;margin-top:6px" value="'+escapeHtml(it.title||'')+'">' + sugg
    + '<textarea data-f="description" '+dis+' rows="6" placeholder="Περιγραφή" style="width:100%;margin-top:6px">'+escapeHtml(it.description||'')+'</textarea>'
    + '<input data-f="tags" '+dis+' placeholder="Tags (με κόμμα)" style="width:100%;margin-top:6px" value="'+escapeHtml(it.tags||'')+'">'
    + '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px"><input data-f="playlist" '+dis+' list="up-pl" placeholder="Playlist (υπάρχον ή νέο όνομα)" style="flex:1;min-width:180px" value="'+escapeHtml(it.playlist||'')+'">'
    + '<label class="meta">Δημοσίευση <input data-f="publish_at" type="datetime-local" '+dis+' value="'+upLocal(it.publish_at)+'"></label></div>';
  return '<div class="qitem" data-id="'+it.id+'" style="display:block"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><strong class="grow">'+escapeHtml(it.path)+'</strong>'+badge+'</div>'
    + fields + prog + err + warn + '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;align-items:center">'+buttons+'<span class="meta">'+link+'</span></div></div>';
}
function drawUploader(){
  $('up-info').textContent = (upData.ready ? '' : 'Λείπει YouTube token για αυτό το κανάλι. ') + 'Φάκελος: ' + upData.inbox + ' · AI: ' + upData.llm + ' · ' + upData.items.length + ' αρχεία';
  if (!$('up-settings').hidden) drawUpSettings();
  const pl = '<datalist id="up-pl"></datalist>';
  $('up-list').innerHTML = (upData.items.length ? upData.items.map(upCard).join('') : '<p class="meta">Ο φάκελος είναι άδειος. Ρίξε βίντεο στο inbox αυτού του καναλιού.</p>') + pl;
  upDirty = false;
  api('/api/uploader/playlists?channel=' + encodeURIComponent(upChannel)).then(d => {
    const dl = $('up-pl'); if (dl) dl.innerHTML = (d.playlists||[]).map(p=>'<option value="'+escapeHtml(p.title)+'">').join('');
  }).catch(()=>{});
}
function upCollect(card){
  const get = n => { const el = card.querySelector('[data-f="'+n+'"]'); return el ? el.value : ''; };
  return {id: Number(card.dataset.id), title: get('title'), description: get('description'), tags: get('tags'), playlist: get('playlist'), publish_at: upIso(get('publish_at'))};
}
async function upPost(path, body){
  try{ await api(path, {method:'POST', body: JSON.stringify(body)}); }
  catch(e){ alert(e.message); }
  await loadUploader();
}
$('up-list').addEventListener('input', () => { upDirty = true; });
$('up-list').addEventListener('click', async e => {
  const card = e.target.closest('.qitem'); if (!card) return;
  const pick = e.target.dataset.pick;
  if (pick !== undefined){
    const it = upData.items.find(x => x.id === Number(card.dataset.id));
    card.querySelector('[data-f="title"]').value = it.suggestions[Number(pick)]; upDirty = true; return;
  }
  const act = e.target.dataset.act; if (!act) return;
  const id = Number(card.dataset.id);
  if (act === 'suggest'){ e.target.textContent = 'Σκέφτομαι…'; e.target.disabled = true; return upPost('/api/uploader/suggest', {id}); }
  if (act === 'save') return upPost('/api/uploader/save', upCollect(card));
  if (act === 'approve'){
    try{ await api('/api/uploader/save', {method:'POST', body: JSON.stringify(upCollect(card))}); }catch(er){ return alert(er.message); }
    return upPost('/api/uploader/approve', {id});
  }
  if (act === 'unapprove') return upPost('/api/uploader/unapprove', {id});
  if (act === 'retry') return upPost('/api/uploader/retry', {id});
  if (act === 'skip' && confirm('Να μεταφερθεί το αρχείο στο _skipped και να φύγει από τη λίστα;')) return upPost('/api/uploader/skip', {id});
});
$('up-scan').onclick = () => loadUploader();
$('up-suggest-all').onclick = () => upPost('/api/uploader/suggest-all', {channel: upChannel});
$('up-reslot').onclick = () => { if (confirm('Να ξαναμοιραστούν οι ημερομηνίες των αρχείων που δεν έχουν εγκριθεί;')) upPost('/api/uploader/reslot', {channel: upChannel}); };
$('up-settings-btn').onclick = () => { const b = $('up-settings'); b.hidden = !b.hidden; if (!b.hidden) drawUpSettings(); };
"""


def _swap(text, old, new, count=1):
    if text.count(old) != count:
        raise RuntimeError("uploader_ui.inject: marker not found %d time(s): %r" % (count, old[:60]))
    return text.replace(old, new)


def inject(page):
    page = _swap(page, '<button type="button" data-tab="history">Ιστορικό</button>',
                 '<button type="button" data-tab="history">Ιστορικό</button>\r\n' + TAB_BUTTON.strip())
    page = _swap(page, '</main>', SECTION + '</main>')
    page = _swap(page, "  $('view-pages').hidden = tab !== 'pages';",
                 "  $('view-pages').hidden = tab !== 'pages';\r\n  $('view-uploader').hidden = tab !== 'uploader';")
    page = _swap(page, "  if (tab === 'pages') loadCampaigns();",
                 "  if (tab === 'pages') loadCampaigns();\r\n  if (tab === 'uploader') loadUploader();")
    page = _swap(page, "  if (tab === 'history'){ box.hidden = true; box.innerHTML = ''; return; }",
                 "  if (tab === 'history'){ box.hidden = true; box.innerHTML = ''; return; }\r\n"
                 "  if (tab === 'uploader'){\r\n"
                 "    if (!upChannel && channels.length) upChannel = channels[0].id;\r\n"
                 "    box.hidden = false;\r\n"
                 "    box.innerHTML = channels.map(c => `<button type=\"button\" class=\"sub ${c.id===upChannel?'on':''}\" data-uch=\"${c.id}\">${escapeHtml(c.label)}</button>`).join('');\r\n"
                 "    return;\r\n  }")
    page = _swap(page, "$('subtabs').onclick = e => {",
                 "$('subtabs').onclick = e => {\r\n"
                 "  const uch = e.target.dataset.uch;\r\n"
                 "  if (uch){ if (uch !== upChannel){ upChannel = uch; upData = null; drawSubtabs(); loadUploader(); } return; }")
    page = _swap(page, '</script></body></html>', JS + '</script></body></html>')
    return page
