# Generated from SiteLang.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SiteLangParser import SiteLangParser
else:
    from SiteLangParser import SiteLangParser

# This class defines a complete listener for a parse tree produced by SiteLangParser.
class SiteLangListener(ParseTreeListener):

    # Enter a parse tree produced by SiteLangParser#site.
    def enterSite(self, ctx:SiteLangParser.SiteContext):
        pass

    # Exit a parse tree produced by SiteLangParser#site.
    def exitSite(self, ctx:SiteLangParser.SiteContext):
        pass


    # Enter a parse tree produced by SiteLangParser#siteBody.
    def enterSiteBody(self, ctx:SiteLangParser.SiteBodyContext):
        pass

    # Exit a parse tree produced by SiteLangParser#siteBody.
    def exitSiteBody(self, ctx:SiteLangParser.SiteBodyContext):
        pass


    # Enter a parse tree produced by SiteLangParser#siteAttr.
    def enterSiteAttr(self, ctx:SiteLangParser.SiteAttrContext):
        pass

    # Exit a parse tree produced by SiteLangParser#siteAttr.
    def exitSiteAttr(self, ctx:SiteLangParser.SiteAttrContext):
        pass


    # Enter a parse tree produced by SiteLangParser#page.
    def enterPage(self, ctx:SiteLangParser.PageContext):
        pass

    # Exit a parse tree produced by SiteLangParser#page.
    def exitPage(self, ctx:SiteLangParser.PageContext):
        pass


    # Enter a parse tree produced by SiteLangParser#pageBody.
    def enterPageBody(self, ctx:SiteLangParser.PageBodyContext):
        pass

    # Exit a parse tree produced by SiteLangParser#pageBody.
    def exitPageBody(self, ctx:SiteLangParser.PageBodyContext):
        pass


    # Enter a parse tree produced by SiteLangParser#pageAttr.
    def enterPageAttr(self, ctx:SiteLangParser.PageAttrContext):
        pass

    # Exit a parse tree produced by SiteLangParser#pageAttr.
    def exitPageAttr(self, ctx:SiteLangParser.PageAttrContext):
        pass


    # Enter a parse tree produced by SiteLangParser#expr.
    def enterExpr(self, ctx:SiteLangParser.ExprContext):
        pass

    # Exit a parse tree produced by SiteLangParser#expr.
    def exitExpr(self, ctx:SiteLangParser.ExprContext):
        pass



del SiteLangParser