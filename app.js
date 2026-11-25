const $ = (s, root=document) => root.querySelector(s);
const api = async (url, options={}) => {
  const response = await fetch(url, {credentials:'same-origin', ...options, headers:{'Content-Type':'application/json', ...(options.headers||{})}});
  const data = await response.json().catch(()=>({error:'Something went wrong.'}));
  if (!response.ok) throw new Error(data.error || 'Something went wrong.');
  return data;
};
const dateLabel = stamp => new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',year:'numeric'}).format(new Date(stamp*1000));
const initials = name => name.split(/\s+/).slice(0,2).map(w=>w[0]).join('').toUpperCase();
let currentUser=null, posts=[], authMode='login', editingId=null, activePost=null;
const authDialog=$('#authDialog'), storyDialog=$('#storyDialog'), postDialog=$('#postDialog');
function showToast(text){const el=$('#toast');el.textContent=text;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2600)}
function escapeHtml(text){return String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function refresh(){
  const [me, listing]=await Promise.all([api('/api/me'),api('/api/posts')]);currentUser=me.user;posts=listing.posts;
  $('#authButton').classList.toggle('hidden',!!currentUser);$('#userChip').classList.toggle('hidden',!currentUser);
  if(currentUser){$('#userChip').innerHTML=`Hi, ${escapeHtml(currentUser.name.split(' ')[0])} <button class="text-button" id="logoutButton">Sign out</button>`;$('#logoutButton').onclick=logout}
  renderPosts();
}
function renderPosts(){
  const grid=$('#storiesGrid');grid.innerHTML='';$('#emptyState').classList.toggle('hidden',posts.length!==0);
  posts.forEach(post=>{
    const card=document.createElement('article');card.className='story-card';card.tabIndex=0;
    card.innerHTML=`<span class="card-kicker">A COMMUNITY STORY &nbsp;·&nbsp; ${dateLabel(post.created_at)}</span><h3>${escapeHtml(post.title)}</h3><p class="excerpt">${escapeHtml(post.body)}</p><div class="card-bottom"><span class="author"><span class="avatar">${escapeHtml(initials(post.author))}</span>${escapeHtml(post.author)}</span><span class="card-meta">${post.comment_count} ${post.comment_count===1?'note':'notes'} &nbsp;→</span></div>`;
    card.onclick=()=>openPost(post.id);card.onkeydown=e=>{if(e.key==='Enter')openPost(post.id)};grid.appendChild(card);
  });
}
function openAuth(mode='login'){authMode=mode;$('#authTitle').textContent=mode==='login'?'Welcome back.':'Make yourself at home.';$('#authIntro').textContent=mode==='login'?'Sign in to share a story or join the conversation.':'Create an account to start sharing your stories.';$('#nameWrap').classList.toggle('hidden',mode==='login');$('#authForm [name=password]').autocomplete=mode==='login'?'current-password':'new-password';$('#authSubmit').innerHTML=mode==='login'?'Sign in &nbsp;→':'Create account &nbsp;→';$('#authSwitch').innerHTML=mode==='login'?'New here? <button type="button">Create an account</button>':'Already have an account? <button type="button">Sign in</button>';$('#authSwitch button').onclick=()=>openAuth(mode==='login'?'register':'login');$('#authError').textContent='';$('#authForm').reset();authDialog.showModal()}
$('#authButton').onclick=()=>openAuth();
async function logout(){await api('/api/logout',{method:'POST'});currentUser=null;await refresh();showToast('You’re signed out. See you soon!')}
function openStory(post=null){if(!currentUser){openAuth();return}editingId=post?.id||null;$('#storyForm').reset();$('#storyError').textContent='';$('.story-modal h2').innerHTML=editingId?'Edit your story<span class="period">.</span>':'Start a new story<span class="period">.</span>';$('.story-modal .form-foot .button').innerHTML=editingId?'Save changes &nbsp;→':'Publish story &nbsp;→';if(post){$('#storyForm [name=title]').value=post.title;$('#storyForm [name=body]').value=post.body}storyDialog.showModal()}
['#writeButton','#emptyWrite','#bannerWrite'].forEach(sel=>$(sel).onclick=()=>openStory());
$('#storyForm').onsubmit=async e=>{e.preventDefault();const form=new FormData(e.currentTarget);const payload={title:form.get('title'),body:form.get('body')};try{if(editingId)await api(`/api/posts/${editingId}`,{method:'PATCH',body:JSON.stringify(payload)});else await api('/api/posts',{method:'POST',body:JSON.stringify(payload)});storyDialog.close();await refresh();showToast(editingId?'Your changes are saved.':'Your story is out in the world.')}catch(err){$('#storyError').textContent=err.message}};
$('#authForm').onsubmit=async e=>{e.preventDefault();const form=new FormData(e.currentTarget),data=Object.fromEntries(form);try{await api(`/api/${authMode==='login'?'login':'register'}`,{method:'POST',body:JSON.stringify(data)});authDialog.close();await refresh();showToast(authMode==='login'?'Welcome back!':'Welcome to The Daily Draft!')}catch(err){$('#authError').textContent=err.message}};
async function openPost(id){activePost=posts.find(p=>p.id===id);if(!activePost)return;const post=activePost;const own=currentUser?.id===post.user_id;const detail=$('#postDetail');detail.innerHTML=`<span class="eyebrow">A COMMUNITY STORY &nbsp;·&nbsp; ${dateLabel(post.created_at)}</span><h2 class="post-detail-title">${escapeHtml(post.title)}</h2><div class="post-detail-meta">By <strong>${escapeHtml(post.author)}</strong> &nbsp;·&nbsp; ${post.comment_count} ${post.comment_count===1?'note':'notes'}</div>${own?'<div class="edit-actions"><button class="text-button" id="editPost">Edit story</button><button class="text-button" id="deletePost">Delete story</button></div>':''}<div class="post-detail-body">${escapeHtml(post.body)}</div><section class="comments"><h3>The conversation</h3><div id="commentList"><p class="card-meta">Loading notes…</p></div><form id="commentForm" class="comment-form"><textarea name="body" placeholder="Leave a kind note…" maxlength="2000" required ${currentUser?'':'disabled'}></textarea><button class="button primary" ${currentUser?'':'disabled'}>Send</button></form>${currentUser?'':'<p class="card-meta">Sign in to leave a note.</p>'}</section>`;
  if(own){$('#editPost').onclick=()=>{postDialog.close();openStory(post)};$('#deletePost').onclick=async()=>{if(!confirm('Delete this story and its comments?'))return;try{await api(`/api/posts/${post.id}`,{method:'DELETE'});postDialog.close();await refresh();showToast('Story deleted.')}catch(err){showToast(err.message)}}}
  await loadComments(post.id);$('#commentForm').onsubmit=async e=>{e.preventDefault();if(!currentUser){openAuth();return}const body=new FormData(e.currentTarget).get('body');try{await api(`/api/posts/${post.id}/comments`,{method:'POST',body:JSON.stringify({body})});e.currentTarget.reset();await loadComments(post.id);await refresh()}catch(err){showToast(err.message)}};postDialog.showModal();
}
async function loadComments(id){const {comments}=await api(`/api/posts/${id}/comments`);const list=$('#commentList');list.innerHTML=comments.length?comments.map(c=>`<div class="comment"><span class="avatar">${escapeHtml(initials(c.author))}</span><div class="comment-body"><strong>${escapeHtml(c.author)} · ${dateLabel(c.created_at)}</strong>${escapeHtml(c.body)}</div></div>`).join(''):'<p class="card-meta">No notes yet. Be the first to leave one.</p>'}
document.querySelectorAll('[data-close]').forEach(btn=>btn.onclick=()=>btn.closest('dialog').close());[authDialog,storyDialog,postDialog].forEach(d=>d.addEventListener('click',e=>{if(e.target===d)d.close()}));
refresh().catch(err=>showToast(err.message));
