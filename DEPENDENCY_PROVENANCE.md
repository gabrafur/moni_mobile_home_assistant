# Dependency provenance

The integration is an independent implementation based on interoperability
testing of the Moni Mobile TCP service. It does not vendor code from Moni,
Intelbras, or Home Assistant.

Runtime dependencies are installed by Home Assistant from the integration
manifest:

| Dependency | Version | Purpose | License | Source |
| --- | --- | --- | --- | --- |
| PyCryptodome | 3.23.0 | AES and PKCS#7 protocol primitives | BSD-2-Clause | <https://www.pycryptodome.org/> |

Home Assistant APIs are imported from the host installation and are not
redistributed by this repository. Moni Mobile product names identify the
interoperated service and do not imply affiliation or endorsement.

The PNG files under `custom_components/moni_mobile/brand/` are resized,
losslessly optimized variants of the official Moni Software site icon from
<https://monisoftware.com.br/wp-content/uploads/2024/03/Icone-do-site.png>.
The trademark remains the property of its owner and is used only to identify
the interoperated product.
