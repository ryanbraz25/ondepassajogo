import asyncio,json
from playwright.async_api import async_playwright
exec(open('shots.py').read().split('async def main')[0])
R="""(sel)=>{const e=document.querySelector(sel);if(!e)return null;const r=e.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top+scrollY),Math.round(r.width),Math.round(r.height)]}"""
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(executable_path='/usr/bin/google-chrome')
    ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page()
    await pg.route('**/*',lambda r:r.abort() if not r.request.url.startswith('file:') else r.continue_())
    await pg.add_init_script("localStorage.setItem('perguntouTime','1');localStorage.setItem('favs','[\"Flamengo\"]')")
    await pg.goto('file:///tmp/t/site/index.html');await prep(pg)
    out={}
    out['day21']=await pg.evaluate(R,'#days .day[data-k="2026-11-21"]')
    await pg.click('#days .day[data-k="2026-11-21"]');await pg.wait_for_timeout(300)
    await pg.click('#chips .chip[data-c="brasileirao-a"]');await pg.wait_for_timeout(300)
    out['chipbra']=await pg.evaluate(R,'#chips .chip[data-c="brasileirao-a"]')
    out['g1']=await pg.evaluate(R,'#list .g, #lista .g')
    out['chans1']=await pg.evaluate(R,'.g .chans')
    out['gratis']=await pg.evaluate(R,'label.free, label:has(input[type=checkbox])')
    out['busca']=await pg.evaluate(R,'#q')
    await pg.click('label:has-text("grátis")');await pg.wait_for_timeout(300)
    out['chans_gr']=await pg.evaluate(R,'.g .chans')
    await pg.goto('file:///tmp/t/site/jogo/palmeiras-x-flamengo-21-11-2026/index.html');await prep(pg)
    out['placa']=await pg.evaluate(R,'.placa');out['botoes']=await pg.evaluate(R,'.botoes');out['h2']=await pg.evaluate(R,'h1')
    print(json.dumps(out))
    await b.close()
asyncio.run(main())
