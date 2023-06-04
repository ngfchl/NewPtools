// ==UserScript==
// @name         PtToPtools-Dev
// @author       ngfchl
// @description  PT站点cookie等信息发送到Ptools
// @namespace    http://tampermonkey.net/

// @match        https://1ptba.com/*
// @match        https://52pt.site/*
// @match        https://audiences.me/*
// @match        https://byr.pt/*
// @match        https://ccfbits.org/*
// @match        https://club.hares.top/*
// @match        https://discfan.net/*
// @match        https://et8.org/*
// @match        https://filelist.io/*
// @match        https://hdatmos.club/*
// @match        https://hdchina.org/*
// @match        https://hdcity.leniter.org/*
// @match        https://hdhome.org/*
// @match        https://hdmayi.com/*
// @match        https://hdsky.me/*
// @match        https://hdtime.org/*
// @match        https://hudbt.hust.edu.cn/*
// @match        https://iptorrents.com/t
// @match        https://kp.m-team.cc/*
// @match        https://lemonhd.org/*
// @match        https://nanyangpt.com/*
// @match        https://npupt.com/*
// @match        https://ourbits.club/*
// @match        https://pt.btschool.club/*
// @match        https://pt.eastgame.org/*
// @match        https://pt.hdbd.us/*
// @match        https://pt.keepfrds.com/*
// @match        https://pterclub.com/*
// @match        https://pthome.net/*
// @match        https://springsunday.net/*
// @match        https://totheglory.im/*
// @match        https://u2.dmhy.org/*
// @match        https://www.beitai.pt/*
// @match        https://www.haidan.video/*
// @match        https://www.hdarea.co/*
// @match        https://www.hddolby.com/*
// @match        https://www.htpt.cc/*
// @match        https://www.nicept.net/*
// @match        https://www.pthome.net/*
// @match        https://www.pttime.org
// @match        https://www.tjupt.org/*
// @match        https://www.torrentleech.org
// @match        https://www.carpet.net/*
// @match        https://wintersakura.net/*
// @match        https://hhanclub.top/*
// @match        https://www.hdpt.xyz/*
// @match        https://ptchina.org/*
// @match        http://www.oshen.win/*
// @match        https://www.hd.ai/*
// @match        http://ihdbits.me/*
// @match        https://zmpt.cc/*
// @match        https://leaves.red/*
// @match        https://piggo.me/*
// @match        https://pt.2xfree.org/*
// @match        https://sharkpt.net/*
// @match        https://www.dragonhd.xyz/*
// @match        https://oldtoons.world/*
// @match        http://hdmayi.com/*
// @match        https://www.3wmg.com/*
// @match        https://carpt.net/*
// @match        https://pt.0ff.cc/*
// @match        https://hdpt.xyz/*
// @match        https://azusa.wiki/*
// @match        https://pt.itzmx.com/*
// @match        https://gamegamept.cn/*
// @match        https://srvfi.top/*
// @match        https://www.icc2022.com/*
// @match        http://leaves.red/*
// @match        https://xingtan.one/*
// @match        http://uploads.ltd/*
// @match        https://cyanbug.net/*
// @match        https://ptsbao.club/*
// @match        https://greatposterwall.com/*
// @match        https://dicmusic.club/*
// @match        https://gainbound.net/*
// @match        http://hdzone.me/*
// @match        https://www.pttime.org/*
// @match        https://pt.msg.vg/*
// @match        https://pt.soulvoice.club/*
// @match        https://www.hitpt.com/*
// @match        https://hdfans.org/*
// @match        https://www.joyhd.net/*
// @match        https://hdzone.me/*
// @match        https://reelflix.xyz/*
// @match        https://pt.hdpost.top/*
// @match        https://monikadesign.uk/*
// @match        https://exoticaz.to/*
// @match        https://cinemaz.to/*
// @match        https://avistaz.to/*
// @match        https://iptorrents.com/*
// @match        https://pt.hdupt.com/*
// @match        https://www.oshen.win/*
// @match        https://hdcity.city/*
// @match        https://hdvideo.one/*
// @match        https://chdbits.co/*
// @match        https://kamept.com/*
// @match        https://ultrahd.net/*
// @match        http://pt.tu88.men/*
// @match        https://pt.hd4fans.org/*

// @match        https://hd-torrents.org/*
// @match        https://fsm.name/*
// @match        https://dajiao.cyou/*
// @match        https://zhuque.in/*
// @match        https://hudbt.hust.edu.cn/*

// @version      0.0.5
// @grant        GM_xmlhttpRequest
// @grant        GM_getResourceURL
// @grant        GM_getResourceText
// @grant        GM_addStyle
// @grant        GM_cookie
// @noframes     true
// @license      GPL-3.0 License
// @require      https://cdn.bootcdn.net/ajax/libs/jquery/3.6.3/jquery.min.js
// @require      https://cdn.bootcdn.net/ajax/libs/twitter-bootstrap/4.6.2/js/bootstrap.min.js

// ==/UserScript==

/*
日志：
    2023.01.28  优化：添加CSS美化代码（其实Copy的bootstrap），优化代码逻辑
    2023.01.28  优化：无须右键菜单，直接在网页显示悬浮窗，点击运行
    2023.01.26  优化：适配站点进一步完善，如遇到PTOOLS支持的站点没有油猴脚本选项，请把网址发给我；优化：取消油猴脚本发送COOKIE的一小时限制
    2023.01.26  修复bug，调整为右键菜单启动
    2023.01.26  更新逻辑，一小时内不会重复更新
    2023.01.25  完成第一版0.0.1
    2023.01.24  开始编写第一版脚本

*/
this.$ = this.jQuery = jQuery.noConflict(true);
/**
 * 小白白们请看这里
 * 需要修改的项目
 * ptools：ptools本地服务端地址，请在此修改设置ptools的访问地址，如http://192.168.1.2:8000
 * token：ptools.toml中设置的token，获取安全密钥token，可以在ptools.toml中自定义，格式 [token] token="ptools"
 * @type {string}
 */
var ptools = "http://192.168.123.5:8001/";
var token = "ptools";
/**
 * 以下内容无需修改
 * @type {string}
 */
var path = "api/monkey/get_site/";
var i = 1;

(function () {
    'use strict';
    if (i == 1) {
        if (window.top != window.self) return; //don't run on frames or iframes
        if (!sessionStorage.getItem(token)) {
            getSite()
        }
        getCss()
        // GM_addStyle(GM_getResourceText("bootstrap"));
        // addStyle()
        // getDownloaders()
        main()
        i++
    }
})();

/**
 * 访问CSS网址并加载
 * @returns null
 */
function getCss() {
    let css = `
        .wrap {
        z-index:99999;
        position: fixed;
        width: 85px;
        margin-right: 0;
        margin-top: 240px;
        float: left;
        opacity: 0.4;
        font-size: 12px;
        background-color: #fff;
        }
        .wrap:hover {
            opacity: 1.0;
        }
        .wrap > img {
            border-radius: 5px;
        }`
    GM_addStyle(css)
    GM_xmlhttpRequest({
        method: "GET",
        url: "https://cdn.bootcdn.net/ajax/libs/twitter-bootstrap/4.6.2/css/bootstrap.min.css", // 替换为你的 CSS 文件的 URL
        onload: function (response) {
            GM_addStyle(response.responseText);
        }
    });
}

/**
 * 获取站点相关规则并写入本地存储
 * @returns {Promise<unknown>}
 */
async function getSite() {
    return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
            url: `${ptools}${path}${token}/${document.location.host}`,
            method: "GET",
            responseType: "json",
            onload: function (response) {
                let res = response.response
                console.log(res)
                if (res.code) {
                    console.log(res.msg)
                    resolve(false)
                }
                sessionStorage.setItem(token, JSON.stringify(res))
                resolve(res)
            },
            onerror: function (response) {
                console.log('服务器连接失败！')
                reject(false)
            }
        })
    })
}

/**
 * 获取Cookie
 * @returns {Promise<unknown>}
 */
async function getCookie() {
    return new Promise((resolve, reject) => {
        GM_cookie('list', { // 异步,如果在return data之前还没执行完，部分站点会导致cookie不全。
            url: location.href
        }, (cookies) => {
            try {
                let ptCookie = cookies.map(c => `${c.name}=${c.value}`).join('; ');
                console.log('【Debug】cookie:', ptCookie);
                resolve(ptCookie)
            } catch (e) {
                reject(false)
            }
        });
    })
}

/**
 * 组装站点信息
 * @returns
 */
async function getSiteData() {
    var site_info = JSON.parse(sessionStorage.getItem(token))
    console.log(site_info)
    if (site_info === false) {
        alert('ptools服务器连接失败！')
        return false;
    }
    console.log(site_info.my_uid_rule)
    //获取cookie与useragent
    let user_agent = window.navigator.userAgent
    let cookie = await getCookie()
    if (!cookie) {
        alert('Cookie获取失败，请使用Beta版油猴（红色图标的油猴）！')
        return false
    }
    //获取UID
    let href = document.evaluate(site_info.my_uid_rule, document).iterateNext().textContent
    console.log(href)
    let user_id_info = href.split('=')
    let user_id = $.trim(user_id_info[user_id_info.length - 1])
    console.log(user_id)
    if (!user_id) {
        alert('用户ID获取失败！')
        return false
    }
    // &token=${token}
    return `user_id=${user_id}&nickname=${site_info.name}&site=${site_info.id}&cookie=${cookie}&user_agent=${user_agent}`
}

/**
 * 保存站点信息到PTools
 * @returns {Promise<unknown>}
 */
async function sync_cookie() {
    await getSite()
    var data = await getSiteData();
    console.log(data)
    if (data) {
        return await send_site_info(data).then(res => {
            return res
        })
    }
}

/**
 * 发送站点信息到PTools
 * @param data
 * @returns {Promise<unknown>}
 */
async function send_site_info(data) {
    return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
            url: `${ptools}api/monkey/save_site/${token}`,
            method: "POST",
            // responseType: "json",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            data: data,
            onload: function (response) {
                console.log(response)
                let res = JSON.parse(response.response)
                console.log(res)
                if (res.code == 0) {
                    console.log(res.msg)
                    resolve(false)
                }
                console.log('站点信息获取成功！', res.msg)
                console.log(res)
                alert('PTools提醒您：' + res.msg)
                resolve(res)
            },
            onerror: function (response) {
                reject("站点信息获取失败")
            }
        })
    })
}

/**
 * 获取下载器列表
 * @returns {Promise<unknown>}
 */
async function getDownloaders() {
    return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
            url: `${ptools}tasks/get_downloaders`,
            method: "GET",
            responseType: "json",
            onload: function (response) {
                let res = response.response
                console.log(res)
                if (res.code) {
                    console.log(res.msg)
                    resolve(false)
                }
                console.log('下载器列表获取成功！', res)

                resolve(res)
            }
        })
    })
}

/**
 * 显示下载器列表
 * @param downloaders
 * @param flag
 * @returns {Promise<string>}
 */
async function showDownloaders(downloaders, flag) {
    let downloader = ''
    downloaders.forEach(item => {
        downloader += `<button class="dropdown-item" data-id="${item.id}">${item.name}</button>`
    })

    let downloader_list = `<div class="btn-group">
                    <button type="button" class="btn btn-outline-warning btn-sm btn-block text-nowrap"
                    style="font-size: 12px;" data-toggle="dropdown" aria-expanded="false">
                        ${flag ? '下载到...' : '下载所有'}
                    </button>
                    <div class="dropdown-menu downloader">
                        ${downloader}
                    </div>
                    </div>`
    if (!flag) {
        downloader_list += `<div class="btn-group">
                    <button type="button" class="btn btn-outline-warning btn-sm btn-block text-nowrap"
                    style="font-size: 12px;" data-toggle="dropdown" aria-expanded="false">
                        下载免费
                    </button>
                    <div class="dropdown-menu download-free">
                        ${downloader}
                    </div>
                    </div>`
    }
    return downloader_list
}

/**
 * 显示页面悬浮窗
 * @returns {Promise<void>}
 */
async function main() {
    var wrap = document.createElement("div");
    var img_url = `${ptools}static/logo.png`;
    var drag = {active: false, offset: {x: 0, y: 0}};

    var first = document.body.firstChild;
    GM_xmlhttpRequest({
        method: "GET",
        url: img_url,
        responseType: "blob",
        onload: function (response) {
            var reader = new FileReader();
            reader.onloadend = function () {
                wrap.innerHTML = `<img src="${reader.result}" style="width: 100%;"><br>
                <div class="btn-group-vertical btn-block action">
                <button type="button" class="btn btn-outline-warning btn-sm btn-block text-nowrap" style="font-size: 12px;" id="sync_cookie">同步Cookie</button>
                <button type="button" class="btn btn-outline-warning btn-sm btn-block text-nowrap" style="font-size: 12px;" id="copy_link">复制链接</button>
                </div>`;
            }
            reader.readAsDataURL(response.response);
        }
    });

    wrap.className = 'wrap'
    var wraphtml = document.body.insertBefore(wrap, first);

    wrap.addEventListener('mousedown', function (event) {
        drag.active = true;
        drag.offset.x = event.clientX - wrap.offsetLeft;
        drag.offset.y = event.clientY - wrap.offsetTop + 240;
        event.preventDefault();
    });

    document.addEventListener('mousemove', function (event) {
        if (drag.active) {
            wrap.style.left = (event.clientX - drag.offset.x) + 'px';
            wrap.style.top = (event.clientY - drag.offset.y) + 'px';
        }
    });

    document.addEventListener('mouseup', function (event) {
        drag.active = false;
    });
    /**
     if (location.pathname.search(/details\w+.php/) > 0
     || location.pathname.includes('/torrent.php')
     || location.pathname.search(/torrents\D*\d+/) > 0
     ) {
            let downloader_list = await getDownloaders()
    console.log(downloader_list)
        console.log('当前为种子详情页')
        let downloaders = await showDownloaders(downloader_list, true)
        $('.action').append(downloaders)
        $('.downloader').on('click', async function (e) {
            const downloader_id = $(this).attr('data-id')
            await download_to(downloader_id)
        })
    }

     if (location.pathname.search(/torrents\D*$/) > 0
     || location.pathname.search(/t$/) > 0
     || location.pathname.includes('/music.php')
     || location.pathname.includes('/torrents.php')) {
            let downloader_list = await getDownloaders()
    console.log(downloader_list)
        console.log('当前为种子列表页')
        let downloaders = await showDownloaders(downloader_list, false)
        $('.action').append(downloaders)
        $('.downloader > button').on('click', async function (e) {
            const downloader_id = $(this).attr('data-id')
            await download_all(downloader_id)
        })
        $('.downloader-free > button').on('click', async function (e) {
            const downloader_id = $(this).attr('data-id')
            await download_free(downloader_id)
        })
    }
     **/
    $('#sync_cookie').on('click', async function () {
        await sync_cookie()
        // await send_site_info()
        // await main()
    })
    // document.getElementById("sync_cookie").onclick = function () {
    //     main()
    // };
    // document.getElementById("download_to").onclick = function () {
    //     download_to()
    // };
    // document.getElementById("download_all").onclick = function () {
    //     download_all()
    // };
    // document.getElementById("copy_link").onclick = function () {
    //     copy_link()
    // };

}

async function download_to(id) {
    alert(`download_to 下载器ID：${id}。失望也是一种幸福，因为还有期待。期待我的到来吧，少年！`)
}

async function download_all(id) {
    alert(`download_all 下载器ID：${id}。失望也是一种幸福，因为还有期待。期待我的到来吧，少年！`)
}

async function download_free(id) {
    alert(`download_free 下载器ID：${id}。失望也是一种幸福，因为还有期待。期待我的到来吧，少年！`)
}

async function copy_link() {
    alert('失望也是一种幸福，因为还有期待。期待我的到来吧，少年！')
}
