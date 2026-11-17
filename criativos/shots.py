import asyncio
from playwright.async_api import async_playwright
FONT="file:///tmp/t/site/fonts-local.css"
async def prep(pg):
    await pg.evaluate("""f=>{const l=document.createElement('link');l.rel='stylesheet';l.href=f;document.head.appendChild(l);
      document.querySelectorAll('link[href^="/"]').forEach(x=>x.href='file:///tmp/t/site'+x.getAttribute('href'));
      document.querySelectorAll('img[src^="/"]').forEach(i=>i.src='file:///tmp/t/site'+i.getAttribute('src'));}""",FONT)
    await pg.evaluate("document.fonts.ready")
    await pg.wait_for_timeout(700)
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome')
    ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page()
    await pg.route('**/*',lambda r:r.abort() if not r.request.url.startswith('file:') else r.continue_())
    await pg.add_init_script("localStorage.setItem('perguntouTime','1');localStorage.setItem('favs','[\"Flamengo\"]')")
    await pg.goto('file:///tmp/t/site/index.html');await prep(pg)
    await pg.click('#days .day[data-k="2026-11-21"]');await pg.wait_for_timeout(400)
    await pg.screenshot(path='/tmp/vid/s_home.jpg',full_page=True,type='jpeg',quality=92)
    await pg.click('#chips .chip[data-c="brasileirao-a"]');await pg.wait_for_timeout(400)
    await pg.evaluate("window.scrollTo(0,0)")
    await pg.screenshot(path='/tmp/vid/s_bra.jpg',full_page=True,type='jpeg',quality=92)
    await pg.click('label:has-text("grátis")');await pg.wait_for_timeout(400)
    await pg.evaluate("window.scrollTo(0,0)")
    await pg.screenshot(path='/tmp/vid/s_gratis.jpg',full_page=True,type='jpeg',quality=92)
    await pg.goto('file:///tmp/t/site/jogo/palmeiras-x-flamengo-21-11-2026/index.html');await prep(pg)
    await pg.evaluate("""()=>document.querySelectorAll('img.cr').forEach(i=>{const t=(i.closest('.tm')||i.parentElement).textContent.trim();const s=document.createElement('span');s.className='cr ini';s.textContent=t.split(/\\s+/).slice(0,2).map(w=>w[0]).join('').toUpperCase().slice(0,2);if(i.closest('.lt'))s.style.cssText='width:22px;height:22px;font-size:10px';i.replaceWith(s)})""")
    await pg.screenshot(path='/tmp/vid/s_jogo.jpg',full_page=True,type='jpeg',quality=92)
    await b.close()
asyncio.run(main())
