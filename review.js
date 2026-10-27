'use strict';
const R=ReviewTools,$=id=>document.getElementById(id);
let manifest=null,hints=[],selected=null,currentImage=null,imageVisible=false,wholeImage=false;
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fields={vegetable_id:'vegetable',price_yen:'price',unit:'unit',valid_from:'startDate',valid_until:'endDate',valid_from_time:'startTime',conditions:'conditions',evidence_text:'evidence'};
function formValues(){const v={};for(const [key,id] of Object.entries(fields))v[key]=$(id).value;v.checks=Object.fromEntries(R.checks.map(k=>[k,$('check-'+k).checked]));return v}
function storageKey(){return 'yasai-review-draft-v1:'+selected.image_sha256+':'+selected.id}
function saveInputs(){if(!selected)return;const v=formValues();delete v.checks;try{localStorage.setItem(storageKey(),JSON.stringify(v))}catch{$('draftStatus').textContent='ブラウザ内への一時保存ができません。入力後に下書きファイルを保存してください。'}}
function paintImage(){
  if(!imageVisible||!selected)return;
  const url=R.sourceUrl(selected.source_url),box=R.focusBox(selected,currentImage);
  if(!box){$('imageArea').innerHTML='<img alt="公式チラシの原本・該当箇所は原本で確認" referrerpolicy="no-referrer" style="width:100%;display:block" src="'+escapeHtml(url)+'">';$('imageMode').disabled=true;return}
  const view=wholeImage?'0 0 '+box.width+' '+box.height:box.viewBox;
  $('imageArea').innerHTML='<svg xmlns="http://www.w3.org/2000/svg" viewBox="'+view+'" role="img" aria-label="公式チラシの原本。赤枠は野菜名の読取位置"><image href="'+escapeHtml(url)+'" width="'+box.width+'" height="'+box.height+'"/><rect x="'+selected.bbox[0]+'" y="'+selected.bbox[1]+'" width="'+selected.bbox[2]+'" height="'+selected.bbox[3]+'" fill="none" stroke="#e32929" stroke-width="5"/></svg>';
  $('imageMode').disabled=false;$('imageMode').textContent=wholeImage?'該当箇所を拡大':'全体を表示';
  const image=$('imageArea').querySelector('image,img');image.addEventListener('error',()=>{$('imageArea').textContent='原本画像を読み込めませんでした。公式の原本を別タブで確認してください。'},{once:true});
}
function chooseCandidate(){
  saveInputs();selected=hints[Number($('candidateSelect').value)];if(!selected)return;
  const previousUrl=currentImage?.source_url;currentImage=manifest.images.find(i=>i.source_url===selected.source_url&&i.sha256===selected.image_sha256);
  if(previousUrl!==selected.source_url)imageVisible=false;wholeImage=false;
  $('originalLink').href=R.sourceUrl(selected.source_url);$('originalLink').hidden=false;$('showImage').disabled=false;
  $('showImage').textContent=imageVisible?'原本画像を再表示':'原本画像を表示';$('imageMode').disabled=!imageVisible;
  const p=currentImage.flyer_period||{};
  $('sourceInfo').textContent='ヤマキシ川北店 / チラシの掲載期間：'+(p.start||'未確認')+'〜'+(p.end||'未確認')+'（商品別の販売日ではありません）';
  $('ocrHint').textContent='読取文字：'+String(selected.evidence_hint||'').slice(0,180)+' / '+(selected.match_method==='one_character_difference'?'野菜名と1文字違うため候補にしました。野菜名も未確定です。':'OCRの文字一致による候補です。商品名・価格は原本で確認してください。');
  $('candidateNotice').textContent=R.focusBox(selected,currentImage)?'原本の該当箇所と全体を切り替えて確認できます。':'この候補には画像サイズ情報がないため、原本の全体を表示します。';
  let saved={};try{saved=JSON.parse(localStorage.getItem(storageKey())||'{}')||{}}catch{}
  for(const [key,id] of Object.entries(fields))$(id).value=typeof saved[key]==='string'?saved[key]:key==='vegetable_id'?selected.vegetable_hint:'';
  for(const k of R.checks)$('check-'+k).checked=false;
  for(const id of ['startDate','endDate']){if(R.realDate(p.start))$(id).min=p.start;else $(id).removeAttribute('min');if(R.realDate(p.end))$(id).max=p.end;else $(id).removeAttribute('max')}
  const expired=R.realDate(p.end)&&new Date(p.end+'T23:59:59+09:00')<new Date();
  $('downloadDraft').disabled=expired;$('draftStatus').textContent=expired?'このチラシは掲載期間を過ぎています。価格登録用の下書きは作成できません。':'';$('draftPreview').textContent='';
  if(imageVisible)paintImage();else $('imageArea').innerHTML='<p class="small" style="padding:20px">「原本画像を表示」で公式サイトから読み込みます。</p>';
}
async function readManifest(){
  const raw='https://raw.githubusercontent.com/64knn5nwdc-bit/yasai-navi/main/review_candidates.json';
  let response=await fetch(raw,{cache:'no-store'}).catch(()=>null);
  if(!response?.ok)response=await fetch('./review_candidates.json',{cache:'no-store'});
  if(!response.ok)throw Error('候補を取得できませんでした。');
  return response.json();
}
async function lastAttemptNote(){
  try{const r=await fetch('https://raw.githubusercontent.com/64knn5nwdc-bit/yasai-navi/main/collection_status.json',{cache:'no-store'});if(!r.ok)return ' 最新の取得状況は確認できません。';const status=await r.json();return status.status==='collection_stopped'?' 最新の取得は停止しています。前回取得分を照合しています。':''}catch{return ' 最新の取得状況は確認できません。'}
}
async function loadReview(){
  $('vegetable').innerHTML=Object.entries(R.vegetables).map(([id,name])=>'<option value="'+id+'">'+name+'</option>').join('');
  try{
    const results=await Promise.all([readManifest(),lastAttemptNote()]);manifest=results[0];hints=R.usableCandidates(manifest);
    if(!hints.length){$('reviewStatus').textContent='現在、照合できる候補はありません。原本確認が必要な価格は掲載しません。';return}
    $('candidateSelect').innerHTML=hints.map((c,i)=>'<option value="'+i+'">'+(i+1)+'. '+R.vegetables[c.vegetable_hint]+'（候補・要確認）</option>').join('');
    $('candidateSelect').disabled=false;
    const checked=manifest.last_success_at?new Date(manifest.last_success_at):null;
    $('reviewStatus').textContent='確認待ち '+hints.length+'件 / 取得成功日時：'+(checked&&!isNaN(checked)?checked.toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'}):'未確認')+' / これは価格の確認日時ではありません。'+results[1];
    chooseCandidate();
  }catch(error){$('reviewStatus').textContent='候補を読み込めませんでした。価格比較へ戻るか、時間をおいて再読込してください。';$('reviewStatus').className='error'}
}
$('candidateSelect').addEventListener('change',chooseCandidate);
$('showImage').addEventListener('click',()=>{imageVisible=true;paintImage()});
$('imageMode').addEventListener('click',()=>{wholeImage=!wholeImage;paintImage()});
$('reviewForm').addEventListener('input',saveInputs);
$('reviewForm').addEventListener('submit',event=>{
  event.preventDefault();$('draftStatus').className='small error';
  try{
    const draft=R.makeDraft(selected,currentImage,formValues());
    const text=JSON.stringify(draft,null,2)+'\n';$('draftPreview').textContent=text;
    const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='yasai-reviewed-'+selected.id+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    $('draftStatus').className='small ok';$('draftStatus').textContent='確認済みの下書きを保存しました。公開価格にはまだ反映されていません。';
  }catch(error){$('draftStatus').textContent=error.message}
});
loadReview();
