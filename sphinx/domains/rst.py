"""
    sphinx.domains.rst
    ~~~~~~~~~~~~~~~~~~

    The reStructuredText domain.

    :copyright: Copyright 2007-2019 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

import re
from typing import cast

from sphinx import addnodes
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, ObjType
from sphinx.locale import _, __
from sphinx.roles import XRefRole
from sphinx.util import logging
from sphinx.util.nodes import make_refnode

if False:
    # For type annotation
    from typing import Any, Dict, Iterator, List, Tuple  # NOQA
    from docutils import nodes  # NOQA
    from sphinx.application import Sphinx  # NOQA
    from sphinx.builders import Builder  # NOQA
    from sphinx.environment import BuildEnvironment  # NOQA


logger = logging.getLogger(__name__)

dir_sig_re = re.compile(r'\.\. (.+?)::(.*)$')


class ReSTMarkup(ObjectDescription):
    """
    Description of generic reST markup.
    """

    def add_target_and_index(self, name, sig, signode):
        # type: (str, str, addnodes.desc_signature) -> None
        targetname = self.objtype + '-' + name
        if targetname not in self.state.document.ids:
            signode['names'].append(targetname)
            signode['ids'].append(targetname)
            signode['first'] = (not self.names)
            self.state.document.note_explicit_target(signode)

            domain = cast(ReSTDomain, self.env.get_domain('rst'))
            domain.note_object(self.objtype, name, location=(self.env.docname, self.lineno))

        indextext = self.get_index_text(self.objtype, name)
        if indextext:
            self.indexnode['entries'].append(('single', indextext,
                                              targetname, '', None))

    def get_index_text(self, objectname, name):
        # type: (str, str) -> str
        if self.objtype == 'directive':
            return _('%s (directive)') % name
        elif self.objtype == 'role':
            return _('%s (role)') % name
        return ''


def parse_directive(d):
    # type: (str) -> Tuple[str, str]
    """Parse a directive signature.

    Returns (directive, arguments) string tuple.  If no arguments are given,
    returns (directive, '').
    """
    dir = d.strip()
    if not dir.startswith('.'):
        # Assume it is a directive without syntax
        return (dir, '')
    m = dir_sig_re.match(dir)
    if not m:
        return (dir, '')
    parsed_dir, parsed_args = m.groups()
    if parsed_args.strip():
        return (parsed_dir.strip(), ' ' + parsed_args.strip())
    else:
        return (parsed_dir.strip(), '')


class ReSTDirective(ReSTMarkup):
    """
    Description of a reST directive.
    """
    def handle_signature(self, sig, signode):
        # type: (str, addnodes.desc_signature) -> str
        name, args = parse_directive(sig)
        desc_name = '.. %s::' % name
        signode += addnodes.desc_name(desc_name, desc_name)
        if len(args) > 0:
            signode += addnodes.desc_addname(args, args)
        return name


class ReSTRole(ReSTMarkup):
    """
    Description of a reST role.
    """
    def handle_signature(self, sig, signode):
        # type: (str, addnodes.desc_signature) -> str
        signode += addnodes.desc_name(':%s:' % sig, ':%s:' % sig)
        return sig


class ReSTDomain(Domain):
    """ReStructuredText domain."""
    name = 'rst'
    label = 'reStructuredText'

    object_types = {
        'directive': ObjType(_('directive'), 'dir'),
        'role':      ObjType(_('role'),      'role'),
    }
    directives = {
        'directive': ReSTDirective,
        'role':      ReSTRole,
    }
    roles = {
        'dir':  XRefRole(),
        'role': XRefRole(),
    }
    initial_data = {
        'objects': {},  # fullname -> docname, objtype
    }  # type: Dict[str, Dict[Tuple[str, str], str]]

    @property
    def objects(self):
        # type: () -> Dict[Tuple[str, str], str]
        return self.data.setdefault('objects', {})  # (objtype, fullname) -> docname

    def note_object(self, objtype, name, location=None):
        # type: (str, str, Any) -> None
        if (objtype, name) in self.objects:
            docname = self.objects[objtype, name]
            logger.warning(__('duplicate description of %s %s, other instance in %s') %
                           (objtype, name, docname), location=location)

        self.objects[objtype, name] = self.env.docname

    def clear_doc(self, docname):
        # type: (str) -> None
        for (typ, name), doc in list(self.objects.items()):
            if doc == docname:
                del self.objects[typ, name]

    def merge_domaindata(self, docnames, otherdata):
        # type: (List[str], Dict) -> None
        # XXX check duplicates
        for (typ, name), doc in otherdata['objects'].items():
            if doc in docnames:
                self.objects[typ, name] = doc

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        # type: (BuildEnvironment, str, Builder, str, str, addnodes.pending_xref, nodes.Element) -> nodes.Element  # NOQA
        objtypes = self.objtypes_for_role(typ)
        for objtype in objtypes:
            todocname = self.objects.get((objtype, target))
            if todocname:
                return make_refnode(builder, fromdocname, todocname,
                                    objtype + '-' + target,
                                    contnode, target + ' ' + objtype)
        return None

    def resolve_any_xref(self, env, fromdocname, builder, target, node, contnode):
        # type: (BuildEnvironment, str, Builder, str, addnodes.pending_xref, nodes.Element) -> List[Tuple[str, nodes.Element]]  # NOQA
        results = []  # type: List[Tuple[str, nodes.Element]]
        for objtype in self.object_types:
            todocname = self.objects.get((objtype, target))
            if todocname:
                results.append(('rst:' + self.role_for_objtype(objtype),
                                make_refnode(builder, fromdocname, todocname,
                                             objtype + '-' + target,
                                             contnode, target + ' ' + objtype)))
        return results

    def get_objects(self):
        # type: () -> Iterator[Tuple[str, str, str, str, str, int]]
        for (typ, name), docname in self.data['objects'].items():
            yield name, name, typ, docname, typ + '-' + name, 1


def setup(app):
    # type: (Sphinx) -> Dict[str, Any]
    app.add_domain(ReSTDomain)

    return {
        'version': 'builtin',
        'env_version': 1,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
