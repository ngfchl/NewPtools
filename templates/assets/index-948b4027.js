import{H as $}from"./core-1978a0f0.js";import{a as k,b as N,c as S,d as j}from"./tools-c5c00c99.js";import{W as M,r as n,d as R,$ as H,f as I,H as q,I as B,U as g,S as v,N as a,M as E,c as F,F as T}from"./vue-8caab7e7.js";import{aj as U,O as V,I as J,ak as O}from"./naiveUI-af4b8138.js";import{b as W}from"./index-a0a5d46f.js";import"./getList-8e4a0623.js";import"./lodash-cc4aae98.js";import"./ionicons5-13bb01b1.js";const z=M("logs",()=>{const s=n([]),l=n(),e=n("logs.log"),_=n(""),o=n(!1),c=n([{label:"请选择"}]),r=async()=>{s.value=await k(),s.value.forEach(t=>{c.value.push({label:t,value:t})})},u=async t=>{o.value=!0,_.value=await N(t),o.value=!1};return{names:s,content:l,currentLog:e,currentLogContent:_,logList:c,loading:o,getNames:r,getLogContent:u,downloadLog:async()=>{await S(e.value)},removeLog:async()=>{o.value=!0,await j(e.value)&&(await r(),e.value="logs.log",await u(e.value)),o.value=!1}}}),A=R({__name:"index",setup(s){const l=z(),{names:e,content:_,currentLog:o,logList:c,loading:r,currentLogContent:u}=H(l),{getNames:p,getLogContent:i,downloadLog:t,removeLog:f}=l;I(async()=>{await p(),await i(o.value)});const L=async d=>{d==="top"&&await i(o.value)},w=async()=>{await i(o.value)};return(d,m)=>{const x=U,h=V,y=J,C=O;return q(),B(T,null,[g(y,{justify:"start",class:"px pt-5px mb-2px"},{default:v(()=>[g(x,{value:a(o),"onUpdate:value":[m[0]||(m[0]=b=>E(o)?o.value=b:null),w],options:a(c),style:{"min-width":"50vw"}},null,8,["value","options"]),g(h,{type:"error",onClick:a(f)},{default:v(()=>[F(" 删除 ")]),_:1},8,["onClick"])]),_:1}),g(C,{loading:a(r),log:a(u),rows:40,hljs:a($),class:"px mt-2 code","line-height":2,onRequireMore:L},null,8,["loading","log","hljs"])],64)}}});const oo=W(A,[["__scopeId","data-v-5e2ec4ed"]]);export{oo as default};