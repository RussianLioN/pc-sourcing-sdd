# T015 traceability

Original product §§10–14 -> EXTRACT-01–07/09. Original Avito-specific payment
requirement and 001-offline/spec verified definition -> EXTRACT-08.
Methodology protected ownership and independent exact-SHA review -> EXTRACT-10.
Concrete test IDs/commands and hashed receipts will be in the handoff gate matrix.
Source section mappings are known; absent original requirement IDs are not invented.
Cost and active user time are unknown. A completed validation workflow does not
prove the original nested runner or full autonomous repair/recovery cycle.

EXTRACT-01/02 -> test_footer_recommendations_and_other_products_do_not_contaminate_selected_product, test_microdata_footer_nested_recommendation_and_other_offer_not_target_claims, test_conflict_inside_selected_product_stays_unresolved.
EXTRACT-03/04 -> test_raw_json_number_lexeme_survives_without_float_rounding, test_conditional_markers_and_price_token_are_retained_in_selected_witness, test_sensitive_price_scalar_is_not_retained_or_normalized.
EXTRACT-05/06 -> test_discontinued_has_original_schema_witness_and_unavailable, test_title_derived_mpn_selector_and_hash_do_not_claim_structured_mpn, test_structured_title_mpn_conflict_or_negation_not_confirmed.
EXTRACT-07 -> test_bridge_journal_restore_preserves_original_price_witness_and_unknowns, actual two retained CLI receipts (historical dates unchanged; no reclassification).
EXTRACT-08 -> test_store_unknown_payment_not_avito_gate_and_avito_preorder_is_manual (unchanged frozen evaluators).
EXTRACT-09 -> existing safe report libfile_6f80550acf948191821952445e27cee7 v0, SHA256 08dd2444a77606e254ef9deecb52c2d108a1e62a24b52b10a86754e57af579e6, no duplicate.
EXTRACT-10 -> test_extraction_preserves_every_parent_byte (230), five negative scope cases. CP-T015-01 original/proposed hashes and 7 counterfactual scope cases; not applied.

EXTRACT-11 -> test_duplicate_top_product_json_members_never_discard_assertions,
test_nested_offer_duplicate_members_are_ambiguous_in_both_orders,
test_nested_array_property_value_and_graph_duplicate_keys_refuse and positive
separate-object control. 24 initial failures preserved, repaired strict object_pairs_hook.
CP-T015-01 applied exact approved hashes; T015 gate reconstructs the literal patch.
