import{h as k,f as w}from"./index-f049c9ad.js";import{d as S,$ as b,r as x,f as v,H as C,I as M,U as s,S as a,N as e,c,F as U}from"./vue-3732522d.js";import{E as z,F as B,am as F}from"./naiveUI-5e433394.js";import"./lodash-18690875.js";import"./ionicons5-ced7f89a.js";const H=S({__name:"index",setup(L){const{isMobile:m,isPad:N,isDesktop:D}=k(),n=w(),{mySiteList:u,mySiteColumns:_}=b(n),{getMySiteList:o,getSiteList:p,editMysite:d,handleUpdateSorter:f}=n,t=x(!1),g=async()=>{t.value=!0,await o(),t.value=!1};return v(async()=>{t.value=!0,await p(),await o(),t.value=!1}),(E,i)=>{const r=z,y=B,h=F;return C(),M(U,null,[s(y,{class:"pt-2 mb-1",justify:"start"},{default:a(()=>[s(r,{size:"small",type:"success",onClick:i[0]||(i[0]=l=>e(d)(0))},{default:a(()=>[c(" 添加 ")]),_:1}),s(r,{size:"small",type:"warning",onClick:g},{default:a(()=>[c(" 刷新 ")]),_:1})]),_:1}),s(h,{columns:e(_),data:e(u),loading:e(t),"min-height":e(m)?520:680,"row-key":l=>l.id,bordered:"","flex-height":"","max-height":"720",size:"small",striped:"","onUpdate:sorter":e(f)},null,8,["columns","data","loading","min-height","row-key","onUpdate:sorter"])],64)}}});export{H as default};