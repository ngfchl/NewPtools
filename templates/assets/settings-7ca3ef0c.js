import{g as r}from"./getList-370f69ba.js";import{k as S,g as m}from"./index-a3975fa5.js";import{W as d,r as a}from"./vue-8caab7e7.js";const{message:s}=m(),h=async()=>await r("config/system"),v=async e=>await r("config/config",e),p=async e=>await r("/config/notify/test",e),T=async e=>{const{msg:n,code:i}=await S("config/config",e);switch(i){case 0:return s==null||s.success(n),!0;default:return s==null||s.error(n),!1}},x=d("settings",()=>{const e=a({index:"root",name:"Root",children:[]}),n=a(""),i=a({title:"NewPTools测试标题",message:"NewPTools测试消息，欢迎使用PTOOLS，玩得开心！"}),g=(t,c)=>{c.children.length=0;for(const o in t){const u={index:o,name:typeof t[o]=="object"?"":t[o],children:[]};c.children.push(u),typeof t[o]=="object"&&g(t[o],u)}},y=async()=>{const t=await h();g(t,e.value)},w=async()=>{await p(i.value)},l=async t=>{n.value=t},f=async t=>{await l(await v({name:t}))};return{getSettingsToml:y,getSettingsFile:f,saveSettingsFile:async t=>{await T({name:t,content:n.value})&&await f(t)},setContent:l,testNotify:w,testMessage:i,content:n,treeData:e}});export{x as u};
