/* Static JavaScript code for the Deploy 'Select' page */

S3.dataTables.initComplete = function() {
    // Move the Deployment Team Select inside the dataTables form
    $('#datatable .bulk-select-options').first().prev().before($('#deploy_application_organisation_id'));
};
