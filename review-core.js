/* Unverified OCR and reviewer drafts never enter the price-comparison data. */
(function(root){
  'use strict';
  const vegetables={cabbage:'キャベツ',onion:'玉ねぎ',negi:'ねぎ',carrot:'にんじん',potato:'じゃがいも',daikon:'大根',tomato:'トマト',cucumber:'きゅうり',hakusai:'白菜',komatsuna:'小松菜',spinach:'ほうれん草'};
  const checks=['store_product','tax_included','quantity','sale_dates','conditions'];
  function sourceUrl(value){
    try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='yamakishi.co.jp'&&!u.port&&!u.username&&!u.password&&!u.search&&!u.hash&&/^\/news\/wp-content\/uploads\/\d{4}\/\d{2}\/\d{4}_(kawakita_omote|shoku_ura|oogata_ura)(-scaled)?\.jpg$/.test(u.pathname)?u.href:null}catch{return null}
  }
  function realDate(value){if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return false;const d=new Date(value+'T00:00:00Z');return !isNaN(d)&&d.toISOString().slice(0,10)===value}
  function usableCandidates(manifest){
    const images=Array.isArray(manifest?.images)?manifest.images:[];
    return (Array.isArray(manifest?.candidates)?manifest.candidates:[]).slice(0,60).filter(c=>c?.store_id==='yamakishi'&&c.review_status==='unverified'&&vegetables[c.vegetable_hint]&&/^[a-f0-9]{24}$/.test(c.id)&&/^[a-f0-9]{64}$/.test(c.image_sha256)&&sourceUrl(c.source_url)&&Array.isArray(c.bbox)&&c.bbox.length===4&&c.bbox.every(Number.isFinite)&&c.bbox[0]>=0&&c.bbox[1]>=0&&c.bbox[2]>0&&c.bbox[3]>0&&images.some(i=>i.source_url===c.source_url&&i.sha256===c.image_sha256));
  }
  function focusBox(c,image){
    const width=image?.width,height=image?.height;
    if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||width>10000||height>10000)return null;
    const [x,y,w,h]=c.bbox;if(x+w>width||y+h>height)return null;
    const left=Math.max(0,x-80),top=Math.max(0,y-80);
    return {width,height,viewBox:[left,top,Math.min(width-left,Math.max(500,w+240)),Math.min(height-top,Math.max(380,h+280))].join(' ')};
  }
  function makeDraft(c,image,values,now=new Date()){
    if(!usableCandidates({images:[image],candidates:[c]}).length)throw Error('候補と原本の対応を確認できません。');
    if(!checks.every(k=>values.checks?.[k]===true))throw Error('原本の確認項目をすべて確認してください。');
    if(!vegetables[values.vegetable_id])throw Error('野菜を選んでください。');
    const price=Number(values.price_yen);
    if(!Number.isFinite(price)||price<=0||!String(values.price_yen).trim()||Math.abs(price*100-Math.round(price*100))>1e-7)throw Error('税込価格を小数第2位までの正の数で入力してください。');
    if(!String(values.unit||'').trim()||!String(values.conditions||'').trim()||!String(values.evidence_text||'').trim())throw Error('数量単位・購入条件・原文の確認根拠を入力してください。');
    const start=values.valid_from,end=values.valid_until,period=image.flyer_period;
    if(!realDate(start)||!realDate(end)||start>end)throw Error('商品ごとの販売開始日・終了日を確認してください。');
    if(!realDate(period?.start)||!realDate(period?.end)||start<period.start||end>period.end)throw Error('販売日が取得したチラシの掲載期間から外れています。');
    if(new Date(end+'T23:59:59+09:00')<now)throw Error('販売期限を過ぎた価格は登録できません。');
    const time=values.valid_from_time||'';
    if(time&&!/^([01]\d|2[0-3]):[0-5]\d$/.test(time))throw Error('開始時刻は日本時間のHH:MMで入力してください。');
    const record={store_id:'yamakishi',vegetable_id:values.vegetable_id,price_yen:price,unit:values.unit.trim(),tax_included:true,valid_from:start,valid_until:end,verified_at:now.toISOString(),source_url:sourceUrl(c.source_url),verification_method:'manual_source_review',evidence_text:values.evidence_text.trim(),conditions:values.conditions.trim(),source_image_sha256:c.image_sha256,review_candidate_id:c.id,review_checks:Object.fromEntries(checks.map(k=>[k,true]))};
    if(time)record.valid_from_time=time;
    return {schema_version:1,publication_status:'draft_not_published',records:[record]};
  }
  const api={vegetables,checks,sourceUrl,realDate,usableCandidates,focusBox,makeDraft};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ReviewTools=api;
})(typeof window!=='undefined'?window:globalThis);
