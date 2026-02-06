 ### 1. Simplify
  - First, let's simplify the problem. There really is no reason we need to handle ships separately from modules. Let's handle both with the same logic. Refactor to handle ship selection and module selection with the same code and
  remove the code that handles them separately.

  ### 2. Key modules based on type_id rather than name
  Second, I strongly suspect that using the module_name as a key for logical operations may be a source of the problem. At the very least it makes it more complicated to solve. We should use the type_id and fit_id to key our backend
   logic, and only use the string module name for user display.
  - When we create the lowest_modules_map in @services/doctrine_service.py, what if we store the lowest modules information as dicts with all the relevant information as keys {type_id: <type_id>, module_name: <type_name>,
  fits_on_market: <fits>, position:<1, 2, or 3>, qty_needed: < (target - fits_on_market) * fit_qty > } where position is the rank order to use when we use for display.
  - Rather than creating the display string in the Dataframe as we currently do in @doctrine_service 799:806, we just store the data and create it in the UI layer (@pages/doctrine_status.py 487:493) by calling keys. Rather than
  parsing strings to extract values for module_name and module_qty, we can just get the values from the dict keys.
  - That gives us a more deterministic way to identify a module, and the market information for a given type_id will be consistent, so can be reused. We only need to use the module_name in the user display.
  - We can also pre-select type_ids that are already selected by storing a type_id when it is selected in a set of selected_type_ids in the session state. We can now set the default value for the check box as true if it is present
  in the session state.
  - adding the qty_needed parameter to use in export csv. for a module, we make qty_needed in the csv the make of qty_needed among the fits using that type_id.
