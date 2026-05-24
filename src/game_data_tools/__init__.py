r"""game_data_tools — convert spreadsheet game data between ``.xlsx`` and ``.json``.

``game_data_tools`` reads ``.xlsx``/``.xlsm`` workbooks described by a project
``config.json`` and emits structured ``.json`` (or ``.csv``/``.tsv``), and writes
the same data back into a workbook for round-tripping. It is a Python port of
`GameDataManager.jl <https://github.com/YongHee-Kim/GameDataManager.jl>`_ and keeps
that tool's config format and conversion semantics.

Public API
==========

- `Project` — load a project from a directory containing ``config.json`` and run
  ``export`` (xlsx → json/csv/tsv) or ``import_json`` (json → xlsx).
- `JSONWorksheet` — the in-memory representation of one converted worksheet.

.. code-block:: python

    from game_data_tools import Project

    project = Project("./MyProject")
    project.export()             # convert every configured workbook
    project.export("items")      # convert one workbook (by filename or stem)
    project.import_json("items") # reverse direction: json -> xlsx

Column names and nesting
========================

A worksheet's header row supplies the keys for each emitted row object. A bare
header such as ``Name`` becomes a top-level key; a header written as a
`JSONPointer <https://datatracker.ietf.org/doc/html/rfc6901>`_ such as
``/stats/hp`` nests the value. Given this sheet:

==========  =============  ===========  ========
Key         Name           /stats/hp    Tags
==========  =============  ===========  ========
WPN001      Steel Sword    10           melee;steel
==========  =============  ===========  ========

the converted row is:

.. code-block:: json

    {
      "Key": "WPN001",
      "Name": "Steel Sword",
      "stats": {"hp": 10},
      "Tags": ["melee", "steel"]
    }

Worksheet ``kwargs`` tutorial
=============================

Each worksheet entry in ``config.json`` may carry a ``kwargs`` object. Its keys
are forwarded verbatim to the workbook reader, so they tune how a single sheet is
parsed. Every option is documented below with a self-contained example.

.. note::

   ``row_oriented: false``, ``squeeze``, and ``omit_null_object`` are accepted by
   the config but **not yet implemented** — the reader raises
   ``NotImplementedError`` for them on purpose, so a project that relies on them
   fails loudly instead of emitting wrong data. They are documented here as the
   intended (and config-compatible) behavior being ported.

``start_line`` (int, default ``1``)
-----------------------------------

The 1-based row that holds the column headers. Rows above it are skipped, so you
can keep a banner or notes row at the top of a designer-facing sheet. With

.. code-block:: json

    {"name": "Equipment", "out": "Items.json", "kwargs": {"start_line": 3}}

rows 1–2 are ignored, row 3 is read as the header, and data starts on row 4.

``delim`` (str or regex, default ``";"``)
-----------------------------------------

The delimiter used to split a single cell into an array. A cell whose text
contains ``delim`` is split and each part is coerced to a scalar
(``int``/``float``/``bool``/``null`` when it looks like one, otherwise the string).
The cell ``melee;steel`` becomes ``["melee", "steel"]``. Pass a different string
to override it, or a regular expression for more complex splitting:

.. code-block:: json

    {"name": "Skills", "out": "Skills.json", "kwargs": {"delim": "\\s*\\|\\s*"}}

Here ``fire | ice | wind`` (with arbitrary surrounding spaces) splits into
``["fire", "ice", "wind"]``.

``empty_value`` (object, default ``{}``)
----------------------------------------

A per-column replacement for empty cells, keyed by column name (or pointer). An
empty cell normally becomes ``null``; if its column appears in ``empty_value``,
the mapped value is substituted instead:

.. code-block:: json

    {
      "name": "Equipment",
      "out": "Items.json",
      "kwargs": {"empty_value": {"Description": "", "Requirements": 0}}
    }

An empty ``Description`` cell yields ``""`` and an empty ``Requirements`` cell
yields ``0`` rather than ``null``. Columns not listed keep the default ``null``.

``row_oriented`` (bool, default ``true``) — *planned*
-----------------------------------------------------

When ``true`` (the default), the header is a row and each subsequent row is one
object — the only mode implemented today. Setting it to ``false`` is meant to read
column-oriented sheets, where the headers run down column A and each *column*
becomes a record. Until that lands, ``{"kwargs": {"row_oriented": false}}`` raises
``NotImplementedError``.

``squeeze`` (bool, default ``false``) — *planned*
-------------------------------------------------

Intended to collapse all rows of a sheet into a single object (rather than a list
of row objects) — useful for sheets that hold one configuration record spread over
several rows. ``{"kwargs": {"squeeze": true}}`` currently raises
``NotImplementedError``.

``omit_null_object`` (bool, default ``false``) — *planned*
----------------------------------------------------------

Intended to drop array elements whose every field is ``null`` after nesting, so
sparse spreadsheet rows do not emit empty placeholder objects.
``{"kwargs": {"omit_null_object": true}}`` currently raises ``NotImplementedError``.

See `JSONWorksheet` and `Project` for the full API.
"""

from .project import Project
from .worksheet import JSONWorksheet

__all__ = ["Project", "JSONWorksheet"]
__version__ = "0.0.1"
