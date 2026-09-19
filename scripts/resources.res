<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE resources
PUBLIC "-//NISO//DTD resource 2005-1//EN" "http://www.daisy.org/z3986/2005/resource-2005-1.dtd">
<resources xmlns="http://www.daisy.org/z3986/2005/resource/" version="2005-1">
   <scope nsuri="http://www.daisy.org/z3986/2005/ncx/">
      <nodeSet id="page-set" select="//smilCustomTest[@bookStruct='PAGE_NUMBER']">
         <resource xml:lang="vi">
            <text>trang</text>
         </resource>
      </nodeSet>
      <nodeSet id="note-set" select="//smilCustomTest[@bookStruct='NOTE']">
         <resource xml:lang="vi">
            <text>chú thích</text>
         </resource>
      </nodeSet>
      <nodeSet id="notref-set" select="//smilCustomTest[@bookStruct='NOTE_REFERENCE']">
         <resource xml:lang="vi">
            <text>chú thích</text>
         </resource>
      </nodeSet>
      <nodeSet id="annot-set" select="//smilCustomTest[@bookStruct='ANNOTATION']">
         <resource xml:lang="vi">
            <text>ghi chú</text>
         </resource>
      </nodeSet>
      <nodeSet id="line-set" select="//smilCustomTest[@bookStruct='LINE_NUMBER']">
         <resource xml:lang="vi">
            <text>dòng</text>
         </resource>
      </nodeSet>
      <nodeSet id="sidebar-set" select="//smilCustomTest[@bookStruct='OPTIONAL_SIDEBAR']">
         <resource xml:lang="vi">
            <text>khung bên</text>
         </resource>
      </nodeSet>
      <nodeSet id="prodnote-set" select="//smilCustomTest[@bookStruct='OPTIONAL_PRODUCER_NOTE']">
         <resource xml:lang="vi">
            <text>chú thích</text>
         </resource>
      </nodeSet>
   </scope>
   <scope nsuri="http://www.w3.org/2001/SMIL20/">
      <nodeSet id="math-seq-set" select="//seq[@class='math']">
         <resource xml:lang="vi">
            <text>công thức toán</text>
         </resource>
      </nodeSet>
      <nodeSet id="math-par-set" select="//par[@class='math']">
         <resource xml:lang="vi">
            <text>công thức toán</text>
         </resource>
      </nodeSet>
   </scope>
</resources>
