import{u}from"./settings-a4de6bd2.js";import{d as F,r as B,_ as N,f as R,G as s,H as V,S as d,R as _,M as t,I as h,a2 as I,Q as i,c as T,a3 as $,L as D,F as E}from"./vue-080993b5.js";import{O as M,I as j,R as G,a7 as H}from"./naiveUI-1e53cf3e.js";import{b as K}from"./index-6c720e4c.js";import"./getList-b7db4d33.js";import"./lodash-5fc50ca6.js";import"./ionicons5-b765452e.js";const L=["textContent"],O=F({__name:"index",setup(Q){const{getSettingsFile:m,saveSettingsFile:f,getSettingsToml:c,setContent:y}=u(),e=B(!1),{treeData:g,content:n}=N(u());R(async()=>{await c()});let l="";const x=async a=>{await m("ptools.toml"),e.value=a,a?l=`${n.value}`:n.value!==l&&await y(l)},v=async()=>{await f("ptools.toml"),e.value=!1,await c()},k=a=>a.index,w=[{type:"selection"},{title:"配置项名称",key:"index"},{title:"值",key:"name"}];return(a,o)=>{const p=M,C=j,S=G,b=H;return s(),V(E,null,[d(C,{justify:"end"},{default:_(()=>[d(p,{type:t(e)?"warning":"primary",onClick:o[0]||(o[0]=r=>x(!t(e)))},{default:_(()=>[h("span",{textContent:I(t(e)?"取消":"编辑")},null,8,L)]),_:1},8,["type"]),t(e)?(s(),i(p,{key:0,type:"success",onClick:v},{default:_(()=>[T(" 保存 ")]),_:1})):$("",!0)]),_:1}),t(e)?(s(),i(S,{key:0,value:t(n),"onUpdate:value":o[1]||(o[1]=r=>D(n)?n.value=r:null),class:"code mt-2",type:"textarea",placeholder:""},null,8,["value"])):(s(),i(b,{key:1,columns:w,data:t(g).children,"row-key":k,"default-expand-all":""},null,8,["data"]))],64)}}});const X=K(O,[["__scopeId","data-v-3e22aab9"]]);export{X as default};
