import{u as c}from"./website-5369ffe2.js";import{d as l,$ as p,r as u,f as _,H as d,R as f,N as t}from"./vue-8caab7e7.js";import{a7 as g}from"./naiveUI-06d71335.js";import"./index-17bc3907.js";import"./lodash-cc4aae98.js";import"./ionicons5-13bb01b1.js";import"./download-b0c18149.js";import"./getList-0dd16dce.js";import"./baseStyle-3d03bd09.js";const z=l({__name:"index",setup(b){const e=c(),{getSiteList:a}=e,{columns:n,siteList:r}=p(e),i=s=>s.id,o=u(!1);return _(async()=>{o.value=!0,await a(),o.value=!1}),(s,w)=>{const m=g;return d(),f(m,{columns:t(n),data:t(r),"row-key":i,size:"small",loading:t(o),bordered:"",striped:""},null,8,["columns","data","loading"])}}});export{z as default};