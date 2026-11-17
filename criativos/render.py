import asyncio,subprocess,sys,os
from playwright.async_api import async_playwright
FPS=30
async def one(b,name,only=None):
    pg=await b.new_page(viewport={'width':1080,'height':1920})
    await pg.goto(f'file:///tmp/vid/{name}.html');await pg.evaluate("window.READY");await pg.wait_for_timeout(800)
    dur=await pg.evaluate("DUR")
    if only is not None:
        for t in only:
            await pg.evaluate(f"render({t})");await pg.screenshot(path=f'/tmp/vid/f_{name}_{t}.jpg',type='jpeg',quality=90)
        await pg.close();return
    tmp=f'/tmp/vid/out/{name}.tmp.mp4'
    ff=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','image2pipe','-framerate',str(FPS),'-c:v','mjpeg','-i','-',
        '-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-shortest','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','96k','-movflags','+faststart',tmp],stdin=subprocess.PIPE)
    n=int(dur*FPS)
    for i in range(n):
        await pg.evaluate(f"render({i/FPS})")
        ff.stdin.write(await pg.screenshot(type='jpeg',quality=92))
    ff.stdin.close();rc=ff.wait()
    if rc==0: os.replace(tmp,f'/tmp/vid/out/{name}.mp4')
    print(name,'ok' if rc==0 else 'FALHOU',n,'quadros',flush=True)
    await pg.close()
async def main():
    os.makedirs('/tmp/vid/out',exist_ok=True)
    args=sys.argv[1:]
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--allow-file-access-from-files'])
        if args and args[0]=='--frames':
            name=args[1];ts=[float(x) for x in args[2:]];await one(b,name,ts)
        else:
            for name in args: await one(b,name)
        await b.close()
asyncio.run(main())
