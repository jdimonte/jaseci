"""
Mix in for jac code object in Jaseci
"""
import json
from jaseci.utils.utils import logger
from jaseci.jac.ir.ast import Ast
import hashlib
from pathlib import Path
from os.path import dirname

# Used to check ir matches grammar of current Jaseci instance
grammar_hash = hashlib.md5(
    Path(dirname(__file__) + "/../jac.g4").read_text().encode()
).hexdigest()


class JacJsonEnc(json.JSONEncoder):
    """Custom Json encoder for Jac ASTs"""

    def default(self, obj):
        if isinstance(obj, Ast):
            retd = {}
            for i in obj.__dict__.keys():
                if not i.startswith("_"):
                    retd[i] = obj.__dict__[i]
            return retd
        return super().default(obj)


class JacJsonDec(json.JSONDecoder):
    """Custom hook for decoding Jac ASTs"""

    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):

        if isinstance(obj, dict) and "mod_name" in obj and "kid" in obj:
            ret = Ast(mod_name=obj["mod_name"], fresh_start=False)
            for i in obj.keys():
                setattr(ret, i, obj[i])
            return ret
        return obj


def jac_ast_to_ir(jac_ast):
    """Convert AST to IR string"""
    return json.dumps(cls=JacJsonEnc, obj={"gram_hash": grammar_hash, "ir": jac_ast})


def jac_ir_to_ast(ir):
    """Convert IR string to AST"""
    ir_load = json.loads(cls=JacJsonDec, s=ir)
    if (
        not isinstance(ir_load, dict)
        or "gram_hash" not in ir_load
        or ir_load["gram_hash"] != grammar_hash
    ):
        logger.error("Jac IR incompatible/outdated with current Jaseci!")
        return ""
    return ir_load["ir"]


class JacCode:
    """Obj mixin to code pickling"""

    def __init__(self, code_ir=None):
        self.is_active = False
        self.code_ir = None
        self.code_sig = None
        self._jac_ast = None
        self.errors = []
        self.apply_ir(code_ir)

    def reset(self):
        self.is_active = False

    def refresh(self):
        self._jac_ast = jac_ir_to_ast(self.code_ir) if self.code_ir else None
        if self._jac_ast:
            self.is_active = True
        else:
            self.is_active = False

    def apply_ir(self, ir):
        """Apply's IR to object"""
        self.code_ir = ir if (isinstance(ir, str)) else jac_ast_to_ir(ir)
        self.code_sig = hashlib.md5(self.code_ir.encode()).hexdigest()
        JacCode.refresh(self)  # should disregard overloaded versions

    def parse_jac(self, code, dir, start_rule="start"):
        """Generate AST tree from Jac code text"""
        tree = Ast(
            jac_text=code, start_rule=start_rule, mod_name=self.name, mod_dir=dir
        )
        self.errors = tree._parse_errors
        if tree._parse_errors:
            logger.error(str(f"{self.name}: Invalid syntax in Jac code!"))
            for i in tree._parse_errors:
                logger.error(i)
            return None
        return tree

    def register(self, code, dir):
        """
        Parses Jac code and saves IR
        """
        start_rule = "start" if self.j_type == "sentinel" else self.j_type
        tree = self.parse_jac(code, dir, start_rule=start_rule)

        if not tree:
            self.is_active = False
        else:
            self.apply_ir(tree)

        if not self.is_active:
            logger.error(str(f"{self.name}: Code not registered"))
        return self.is_active

    def ir_dict(self):
        """Return IR as dictionary"""
        return json.loads(self.code_ir)
