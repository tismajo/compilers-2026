# Generated from SiteLang.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,11,51,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,1,1,1,5,1,24,8,1,10,1,12,1,27,9,
        1,1,2,1,2,1,2,1,2,1,3,1,3,1,3,1,3,1,3,1,3,1,4,5,4,40,8,4,10,4,12,
        4,43,9,4,1,5,1,5,1,5,1,5,1,6,1,6,1,6,0,0,7,0,2,4,6,8,10,12,0,1,1,
        0,6,8,46,0,14,1,0,0,0,2,25,1,0,0,0,4,28,1,0,0,0,6,32,1,0,0,0,8,41,
        1,0,0,0,10,44,1,0,0,0,12,48,1,0,0,0,14,15,5,1,0,0,15,16,5,8,0,0,
        16,17,5,2,0,0,17,18,3,2,1,0,18,19,5,3,0,0,19,20,5,0,0,1,20,1,1,0,
        0,0,21,24,3,4,2,0,22,24,3,6,3,0,23,21,1,0,0,0,23,22,1,0,0,0,24,27,
        1,0,0,0,25,23,1,0,0,0,25,26,1,0,0,0,26,3,1,0,0,0,27,25,1,0,0,0,28,
        29,5,9,0,0,29,30,5,4,0,0,30,31,3,12,6,0,31,5,1,0,0,0,32,33,5,5,0,
        0,33,34,5,8,0,0,34,35,5,2,0,0,35,36,3,8,4,0,36,37,5,3,0,0,37,7,1,
        0,0,0,38,40,3,10,5,0,39,38,1,0,0,0,40,43,1,0,0,0,41,39,1,0,0,0,41,
        42,1,0,0,0,42,9,1,0,0,0,43,41,1,0,0,0,44,45,5,9,0,0,45,46,5,4,0,
        0,46,47,3,12,6,0,47,11,1,0,0,0,48,49,7,0,0,0,49,13,1,0,0,0,3,23,
        25,41
    ]

class SiteLangParser ( Parser ):

    grammarFileName = "SiteLang.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'site'", "'{'", "'}'", "'='", "'page'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "BOOLEAN", "NUMBER", "STRING", 
                      "IDENTIFIER", "COMMENT", "WS" ]

    RULE_site = 0
    RULE_siteBody = 1
    RULE_siteAttr = 2
    RULE_page = 3
    RULE_pageBody = 4
    RULE_pageAttr = 5
    RULE_expr = 6

    ruleNames =  [ "site", "siteBody", "siteAttr", "page", "pageBody", "pageAttr", 
                   "expr" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    BOOLEAN=6
    NUMBER=7
    STRING=8
    IDENTIFIER=9
    COMMENT=10
    WS=11

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class SiteContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(SiteLangParser.STRING, 0)

        def siteBody(self):
            return self.getTypedRuleContext(SiteLangParser.SiteBodyContext,0)


        def EOF(self):
            return self.getToken(SiteLangParser.EOF, 0)

        def getRuleIndex(self):
            return SiteLangParser.RULE_site

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterSite" ):
                listener.enterSite(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitSite" ):
                listener.exitSite(self)




    def site(self):

        localctx = SiteLangParser.SiteContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_site)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 14
            self.match(SiteLangParser.T__0)
            self.state = 15
            self.match(SiteLangParser.STRING)
            self.state = 16
            self.match(SiteLangParser.T__1)
            self.state = 17
            self.siteBody()
            self.state = 18
            self.match(SiteLangParser.T__2)
            self.state = 19
            self.match(SiteLangParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SiteBodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def siteAttr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SiteLangParser.SiteAttrContext)
            else:
                return self.getTypedRuleContext(SiteLangParser.SiteAttrContext,i)


        def page(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SiteLangParser.PageContext)
            else:
                return self.getTypedRuleContext(SiteLangParser.PageContext,i)


        def getRuleIndex(self):
            return SiteLangParser.RULE_siteBody

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterSiteBody" ):
                listener.enterSiteBody(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitSiteBody" ):
                listener.exitSiteBody(self)




    def siteBody(self):

        localctx = SiteLangParser.SiteBodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_siteBody)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 25
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==5 or _la==9:
                self.state = 23
                self._errHandler.sync(self)
                token = self._input.LA(1)
                if token in [9]:
                    self.state = 21
                    self.siteAttr()
                    pass
                elif token in [5]:
                    self.state = 22
                    self.page()
                    pass
                else:
                    raise NoViableAltException(self)

                self.state = 27
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SiteAttrContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(SiteLangParser.IDENTIFIER, 0)

        def expr(self):
            return self.getTypedRuleContext(SiteLangParser.ExprContext,0)


        def getRuleIndex(self):
            return SiteLangParser.RULE_siteAttr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterSiteAttr" ):
                listener.enterSiteAttr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitSiteAttr" ):
                listener.exitSiteAttr(self)




    def siteAttr(self):

        localctx = SiteLangParser.SiteAttrContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_siteAttr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 28
            self.match(SiteLangParser.IDENTIFIER)
            self.state = 29
            self.match(SiteLangParser.T__3)
            self.state = 30
            self.expr()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PageContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(SiteLangParser.STRING, 0)

        def pageBody(self):
            return self.getTypedRuleContext(SiteLangParser.PageBodyContext,0)


        def getRuleIndex(self):
            return SiteLangParser.RULE_page

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPage" ):
                listener.enterPage(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPage" ):
                listener.exitPage(self)




    def page(self):

        localctx = SiteLangParser.PageContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_page)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 32
            self.match(SiteLangParser.T__4)
            self.state = 33
            self.match(SiteLangParser.STRING)
            self.state = 34
            self.match(SiteLangParser.T__1)
            self.state = 35
            self.pageBody()
            self.state = 36
            self.match(SiteLangParser.T__2)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PageBodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def pageAttr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(SiteLangParser.PageAttrContext)
            else:
                return self.getTypedRuleContext(SiteLangParser.PageAttrContext,i)


        def getRuleIndex(self):
            return SiteLangParser.RULE_pageBody

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPageBody" ):
                listener.enterPageBody(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPageBody" ):
                listener.exitPageBody(self)




    def pageBody(self):

        localctx = SiteLangParser.PageBodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_pageBody)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 41
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==9:
                self.state = 38
                self.pageAttr()
                self.state = 43
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PageAttrContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENTIFIER(self):
            return self.getToken(SiteLangParser.IDENTIFIER, 0)

        def expr(self):
            return self.getTypedRuleContext(SiteLangParser.ExprContext,0)


        def getRuleIndex(self):
            return SiteLangParser.RULE_pageAttr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPageAttr" ):
                listener.enterPageAttr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPageAttr" ):
                listener.exitPageAttr(self)




    def pageAttr(self):

        localctx = SiteLangParser.PageAttrContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_pageAttr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 44
            self.match(SiteLangParser.IDENTIFIER)
            self.state = 45
            self.match(SiteLangParser.T__3)
            self.state = 46
            self.expr()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(SiteLangParser.STRING, 0)

        def NUMBER(self):
            return self.getToken(SiteLangParser.NUMBER, 0)

        def BOOLEAN(self):
            return self.getToken(SiteLangParser.BOOLEAN, 0)

        def getRuleIndex(self):
            return SiteLangParser.RULE_expr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpr" ):
                listener.enterExpr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpr" ):
                listener.exitExpr(self)




    def expr(self):

        localctx = SiteLangParser.ExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_expr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 48
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 448) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





