/* The Roots & Routes page, served bare for framing on a person's page (the kit's PersonRootsViews.astro).
   #<view>&p=<id>&embed=1 hides the site chrome, the Record Atlas banner, the description row and the filters, so only the view shows.
   #profile&p=<id>&embed=1 shows the person's own panel (the Atlas places, the route, what changed around them, what is missing,
   where to look) full width, and every other view is the chart alone (the panel is hidden: that section is already on the page), in a reading order, with the parts the person page already has left out; it reports its height to the
   parent page so the frame is exactly as tall as its content. The panel's content is the viewer's own, so the two never disagree. */
import page from "../../../../data/tree-page/roots.html?raw";

const EMBED = `<script>
(function(){
  var h=location.hash, emb=/[#&]embed=1/.test(h), prof=/^#profile\\b/.test(h);
  if(!emb)return;
  document.documentElement.classList.add("emb"); if(prof)document.documentElement.classList.add("emb-profile");
  if(!prof)return;
  var ORDER=[/^places/,/^the whole route/,/^around their/,/^what is missing/,/^where to look|^sources/];
  var busy=false;
  function say(){try{var pp=document.getElementById("panel");parent.postMessage({rrh:pp?Math.ceil(pp.getBoundingClientRect().bottom+window.scrollY)+8:document.documentElement.scrollHeight,pid:(h.match(/[#&]p=([^&]+)/)||[])[1]},"*")}catch(e){}}
  function regroup(){
    var p=document.getElementById("panel"); if(!p||busy||p.querySelector(".rrg"))return; busy=true;
    var groups=[],cur={t:"head",n:[]}; groups.push(cur);
    [].slice.call(p.childNodes).forEach(function(n){ if(n.nodeType===1&&n.tagName==="H3"){cur={t:n.textContent.trim().toLowerCase(),n:[]};groups.push(cur)} cur.n.push(n) });
    var out=[]; ORDER.forEach(function(re){ groups.forEach(function(g){ if(re.test(g.t)&&out.indexOf(g)<0)out.push(g) }) });
    p.innerHTML="";
    out.forEach(function(g){ var s=document.createElement("section"); s.className="rrg"; g.n.forEach(function(n){s.appendChild(n)}); p.appendChild(s) });
    busy=false; say();
  }
  document.addEventListener("DOMContentLoaded",function(){
    var p=document.getElementById("panel"); if(!p)return;
    new MutationObserver(function(){regroup()}).observe(p,{childList:true});
    regroup(); window.addEventListener("load",function(){setTimeout(say,300);setTimeout(say,1500)}); window.addEventListener("resize",say);
  });
})();
</script>
<style>
.emb header.top,.emb #metrics,.emb nav.tabs,.emb .atlasbar,.emb .toolrow{display:none!important}
.emb body{padding-top:0}.emb .wrap{padding-top:.4rem;margin-top:0}
.emb:not(.emb-profile) #panel{display:none!important}
.emb:not(.emb-profile) .layout{display:block!important;grid-template-columns:1fr!important}
.emb-profile .layout>:not(#panel){display:none!important}
.emb-profile .layout{display:block!important}
.emb-profile #panel{position:static!important;width:auto!important;max-width:none!important;height:auto!important;max-height:none!important;overflow:visible!important;
  border:0!important;box-shadow:none!important;background:transparent!important;padding:0!important;columns:2 24rem;column-gap:2.6rem;zoom:1.2}
.emb-profile #panel .rrg{break-inside:avoid;margin:0 0 1.6rem}
.emb-profile #panel .plcs{grid-template-columns:minmax(0,1fr)}   /* each place has the whole column: the map and the name above, the regime, records and links across the full width */
.emb-profile #panel .rrg>h3:first-child{margin-top:0}
</style>`;

export const GET = () =>
  new Response(page.replace(/<head>/i, (h) => h + EMBED), { headers: { "content-type": "text/html; charset=utf-8" } });
