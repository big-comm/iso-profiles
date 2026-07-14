#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
pot_file="${script_dir}/bigcommunity-grub.pot"
po_dir="${script_dir}/po"
# manjaro-tools copies /usr/share/grub/locales into the ISO's /boot/grub.
mo_dir="${repo_root}/shared/live-overlay/usr/share/grub/locales/bigcommunity"
minimal_mo_dir="${repo_root}/bigcommunity/minimal/live-overlay/usr/share/grub/locales/bigcommunity"

sources=(
    "shared/live-overlay/usr/share/grub/cfg/grub.cfg"
    "shared/live-overlay/usr/share/grub/cfg/kernels.cfg"
    "shared/live-overlay/usr/share/grub/cfg/languages.cfg"
    "bigcommunity/minimal/live-overlay/usr/share/grub/cfg/kernels.cfg"
)

mkdir -p "${po_dir}" "${mo_dir}" "${minimal_mo_dir}"

(
    cd "${repo_root}"
    xgettext \
        --language=Shell \
        --from-code=UTF-8 \
        --package-name=bigcommunity-grub \
        --package-version=1 \
        --msgid-bugs-address=https://github.com/BigCommunity/iso-profiles/issues \
        --copyright-holder=BigCommunity \
        --no-wrap \
        --output="${pot_file}" \
        "${sources[@]}"
)

for locale in $(<"${script_dir}/LINGUAS"); do
    po_file="${po_dir}/${locale}.po"
    if [[ ! -s "${po_file}" ]]; then
        msginit --no-translator --input="${pot_file}" --locale="${locale}.UTF-8" --output-file="${po_file}"
    else
        msgmerge --update --backup=none --no-wrap "${po_file}" "${pot_file}"
        msgattrib --no-obsolete --no-wrap --output-file="${po_file}" "${po_file}"
    fi
    sed -i -E 's/charset=(ASCII|CHARSET)/charset=UTF-8/' "${po_file}"
    msgfmt --check "${po_file}" --output-file="${mo_dir}/${locale}.mo"
    cp "${mo_dir}/${locale}.mo" "${minimal_mo_dir}/${locale}.mo"
done
