"""委托评估机构申请材料核验场景的规则定义。"""

from app.business.online.domain.checklist.definitions import (
    ChecklistRequirementComponent,
    ChecklistRequirementDefinition,
    ChecklistScenarioDefinition,
)

COURT_EVALUATION_MATERIALS_SCENARIO = ChecklistScenarioDefinition(
    scenario_code="court-evaluation-materials-review",
    scenario_name="委托评估机构申请材料核验",
    retrieval_query="申请参与委托评估的机构应提交哪些资料",
    policy_category="收费标准",
    min_rule_match_count=8,
    requirements=(
        ChecklistRequirementDefinition(
            field_key="application_form_and_profile",
            label="申请书（登记表）及机构简介",
            components=(
                ChecklistRequirementComponent(label="申请书或登记表", aliases=("申请书", "登记表")),
                ChecklistRequirementComponent(label="机构简介", aliases=("机构简介",)),
            ),
            evidence_keywords=("申请书", "登记表", "机构简介"),
        ),
        ChecklistRequirementDefinition(
            field_key="business_license_and_tax_registration",
            label="企业法人营业执照副本和税务登记证副本",
            components=(
                ChecklistRequirementComponent(
                    label="企业法人营业执照副本",
                    aliases=("企业法人营业执照副本", "营业执照副本", "营业执照"),
                ),
                ChecklistRequirementComponent(
                    label="税务登记证副本",
                    aliases=("税务登记证副本", "税务登记证"),
                ),
            ),
            evidence_keywords=("企业法人营业执照副本", "税务登记证副本"),
        ),
        ChecklistRequirementDefinition(
            field_key="institution_qualification",
            label="机构资质、资格证书副本",
            components=(
                ChecklistRequirementComponent(
                    label="机构资质、资格证书副本",
                    aliases=("机构资质", "资质证书副本", "资格证书副本"),
                ),
            ),
            evidence_keywords=("机构资质", "资格证书副本"),
        ),
        ChecklistRequirementDefinition(
            field_key="staff_roster_and_premises_proof",
            label="机构评估（审计）人员名单及其相关资质、机构营业场所证明资料",
            components=(
                ChecklistRequirementComponent(
                    label="评估（审计）人员名单",
                    aliases=("评估人员名单", "审计人员名单", "人员名单"),
                ),
                ChecklistRequirementComponent(
                    label="相关资质",
                    aliases=("相关资质", "人员资质", "人员资格"),
                ),
                ChecklistRequirementComponent(
                    label="机构营业场所证明资料",
                    aliases=("机构营业场所证明资料", "营业场所证明资料", "营业场所证明"),
                ),
            ),
            evidence_keywords=("人员名单", "相关资质", "营业场所证明资料"),
        ),
        ChecklistRequirementDefinition(
            field_key="qualification_certificate_copy",
            label="资格证书副本",
            components=(
                ChecklistRequirementComponent(
                    label="资格证书副本", aliases=("资格证书副本", "资格证书")
                ),
            ),
            evidence_keywords=("资格证书副本",),
        ),
        ChecklistRequirementDefinition(
            field_key="capital_contribution_and_asset_details",
            label="注资证明及资产明细表",
            components=(
                ChecklistRequirementComponent(label="注资证明", aliases=("注资证明",)),
                ChecklistRequirementComponent(
                    label="资产明细表", aliases=("资产明细表", "资产明细")
                ),
            ),
            evidence_keywords=("注资证明", "资产明细表"),
        ),
        ChecklistRequirementDefinition(
            field_key="tax_certificate",
            label="税务机关出具的纳税证明",
            components=(ChecklistRequirementComponent(label="纳税证明", aliases=("纳税证明",)),),
            evidence_keywords=("纳税证明",),
        ),
        ChecklistRequirementDefinition(
            field_key="other_court_required_materials",
            label="法院指定提交的其他资料",
            components=(
                ChecklistRequirementComponent(
                    label="法院指定提交的其他资料",
                    aliases=("法院指定提交的其他资料", "法院指定资料", "其他资料"),
                ),
            ),
            evidence_keywords=("法院指定提交的其他资料",),
        ),
    ),
)
