#!/bin/bash
#
# packaging.sh  Copyright (C) 2019 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>

# shellcheck disable=SC1091
. .travis/common.sh

checkcmd pip find zipinfo diff

function finish {
  rm -Rf sources package "$tmp"
}
trap finish EXIT

tmp=$(mktemp -d)

pip wheel --no-deps -w "$tmp" .
find openquake/ -type f ! -name \*.pyc | grep -Ev 'openquake/__init__.py|/tests/|nrml_examples' | sort > sources
zipinfo -1 "$tmp"/openquake.engine*.whl | grep '^openquake/' | grep -v 'nrml_examples' | sort > package
diff -uN sources package
