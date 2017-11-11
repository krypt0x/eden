# -*- coding: utf-8 -*-

""" Sahana Eden Data Collection Models
    - a front-end UI to manage Assessments which uses the Dynamic Tables
      back-end

    @copyright: 2014-2017 (c) Sahana Software Foundation
    @license: MIT

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.
"""

__all__ = ("DataCollectionTemplateModel",
           "DataCollectionModel",
           "dc_rheader",
           "dc_target_check",
           )

from gluon import *
from gluon.languages import read_dict, write_dict

from ..s3 import *
from s3layouts import S3PopupLink

# =============================================================================
class DataCollectionTemplateModel(S3Model):
    """
        Templates to use for Assessments / Surveys
        - uses the Dynamic Tables back-end to store Questions
    """

    names = ("dc_template",
             "dc_template_id",
             "dc_section",
             "dc_question",
             "dc_question_l10n",
             )

    def model(self):

        T = current.T
        db = current.db

        crud_strings = current.response.s3.crud_strings
        settings = current.deployment_settings

        add_components = self.add_components
        configure = self.configure
        define_table = self.define_table

        UNKNOWN_OPT = current.messages.UNKNOWN_OPT

        # =====================================================================
        # Data Collection Templates
        #
        tablename = "dc_template"
        define_table(tablename,
                     Field("name",
                           label = T("Name"),
                           requires = IS_NOT_EMPTY(),
                           ),
                     # The Dynamic Table used to store the Questions and Answers
                     # (An alternative design would be to use Tables as reusable
                     #  Sections but this hasn't been adopted at this time for
                     #  simplicity)
                     self.s3_table_id(
                        readable = False,
                        writable = False,
                        ),
                     s3_comments(),
                     *s3_meta_fields())

        configure(tablename,
                  create_onaccept = self.dc_template_create_onaccept,
                  deduplicate = S3Duplicate(),
                  )

        # Reusable field
        represent = S3Represent(lookup=tablename)
        template_id = S3ReusableField("template_id", "reference %s" % tablename,
                                      label = T("Template"),
                                      represent = represent,
                                      requires = IS_ONE_OF(db, "dc_template.id",
                                                           represent,
                                                           ),
                                      sortby = "name",
                                      comment = S3PopupLink(f="template",
                                                            tooltip=T("Add a new data collection template"),
                                                            ),
                                      )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Template"),
            title_display = T("Template Details"),
            title_list = T("Templates"),
            title_update = T("Edit Template"),
            label_list_button = T("List Templates"),
            label_delete_button = T("Delete Template"),
            msg_record_created = T("Template added"),
            msg_record_modified = T("Template updated"),
            msg_record_deleted = T("Template deleted"),
            msg_list_empty = T("No Templates currently registered"))

        # Components
        add_components(tablename,
                       dc_question = "template_id",
                       dc_section = "template_id",
                       )

        # =====================================================================
        # Template Sections
        #
        #Currently support Sections, SubSections & SubSubSections only
        #
        hierarchical_sections = True # @ToDo: deployment_setting

        tablename = "dc_section"
        define_table(tablename,
                     template_id(),
                     Field("parent", "reference dc_section",
                           label = T("SubSection of"),
                           ondelete = "RESTRICT",
                           readable = hierarchical_sections,
                           writable = hierarchical_sections,
                           ),
                     Field("name",
                           label = T("Name"),
                           requires = IS_NOT_EMPTY(),
                           ),
                     Field("posn", "integer",
                           label = T("Position"),
                           ),
                     s3_comments(),
                     *s3_meta_fields())

        # Reusable field
        represent = S3Represent(lookup=tablename)
        requires = IS_EMPTY_OR(IS_ONE_OF(db, "dc_section.id",
                                         represent,
                                         ))
        if hierarchical_sections:
            hierarchy = "parent"
            # Can't be defined in-line as otherwise get a circular reference
            parent = db[tablename].parent
            parent.represent = represent
            parent.requires = requires

            widget = S3HierarchyWidget(lookup = tablename,
                                       represent = represent,
                                       multiple = False,
                                       leafonly = True,
                                       )
        else:
            hierarchy = None
            widget = None

        section_id = S3ReusableField("section_id", "reference %s" % tablename,
                                     label = T("Section"),
                                     represent = represent,
                                     requires = requires,
                                     sortby = "name",
                                     widget = widget,
                                     #comment = S3PopupLink(f="template",
                                     #                      args=["[id]", "section"], # @ToDo: Build support for this?
                                     #                      tooltip=T("Add a new section to the template"),
                                     #                      ),
                                     )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Section"),
            title_display = T("Section Details"),
            title_list = T("Sections"),
            title_update = T("Edit Section"),
            label_list_button = T("List Sections"),
            label_delete_button = T("Delete Section"),
            msg_record_created = T("Section added"),
            msg_record_modified = T("Section updated"),
            msg_record_deleted = T("Section deleted"),
            msg_list_empty = T("No Sections currently registered"))

        configure(tablename,
                  deduplicate = S3Duplicate(primary=("name", "parent", "template_id")),
                  hierarchy = hierarchy,
                  orderby = tablename + ".posn",
                  )

        # =====================================================================
        # Questions
        #
        type_opts = {1: T("Text"),
                     2: T("Number"),
                     #3: T("Fractional Number"),
                     4: T("Yes/No"),
                     5: T("Yes, No, Don't Know"),
                     6: T("Options"),
                     7: T("Date"),
                     #8: T("Date/Time"),
                     9: T("Grid"), # Pseudo-question
                     #: T("Organization"),
                     #: T("Location"),
                     #: T("Person"),
                     }

        tablename = "dc_question"
        define_table(tablename,
                     template_id(),
                     section_id(),
                     Field("posn", "integer",
                           label = T("Position"),
                           ),
                     Field("name",
                           label = T("Name"),
                           requires = IS_NOT_EMPTY(),
                           ),
                     Field("code",
                           label = T("Code"),
                           requires = IS_EMPTY_OR(
                                        # Only really needs to be unique per Template
                                        IS_NOT_IN_DB(db, "dc_question.code")
                                        ),
                           comment = DIV(_class="tooltip",
                                         _title="%s|%s" % (T("Code"),
                                                           T("Unique code for the field - required if using Auto-Totals or Grids"),
                                                           ),
                                         ),
                           ),
                     # The Dynamic Field used to store the Question/Answers
                     self.s3_field_id(
                        readable = False,
                        writable = False,
                        ),
                     Field("field_type", "integer", notnull=True,
                           default = 1, # string
                           label = T("Field Type"),
                           represent = lambda opt: \
                                            type_opts.get(opt, UNKNOWN_OPT),
                           requires = IS_IN_SET(type_opts),
                           ),
                     Field("options", "json",
                           label = T("Options"),
                           requires = IS_EMPTY_OR(IS_JSONS3()),
                           ),
                     # Use List to force order or Dict to alphasort
                     #Field("sort_options", "boolean",
                     #      default = True,
                     #      label = T("Sort Options?"),
                     #      represent = s3_yes_no_represent,
                     #      comment = DIV(_class="tooltip",
                     #                    _title="%s|%s" % (T("Sort Options?"),
                     #                                      T("Whether options should be sorted alphabetically"),
                     #                                      ),
                     #                    ),
                     #      ),
                     Field("grid", "json",
                           label = T("Grid"),
                           requires = IS_EMPTY_OR(IS_JSONS3()),
                           comment = DIV(_class="tooltip",
                                         _title="%s|%s%s" % (T("Grid"),
                                                             T("For Grid Pseudo-Question, this is the Row labels & Column labels"),
                                                             T("For Questions within the Grid, this is their position in the Grid, encoded as Grid,Row,Col"), # @ToDo: Widget?
                                                             ),
                                         ),
                           ),
                     Field("totals", "json",
                           label = T("Totals"),
                           requires = IS_EMPTY_OR(IS_JSONS3()),
                           comment = DIV(_class="tooltip",
                                         _title="%s|%s" % (T("Totals"),
                                                           T("List of fields (codes) which this one is the Total of"),
                                                           ),
                                         ),
                           ),
                     Field("require_not_empty", "boolean",
                           default = False,
                           label = T("Required?"),
                           represent = s3_yes_no_represent,
                           comment = DIV(_class="tooltip",
                                         _title="%s|%s" % (T("Required?"),
                                                           T("Is the field mandatory? (Cannot be left empty)"),
                                                           ),
                                         ),
                           ),
                     s3_comments(label = T("Tooltip"),
                                 represent = s3_text_represent,
                                 comment = DIV(_class="tooltip",
                                               _title="%s|%s" % (T("Tooltip"),
                                                                 T("Explanation of the field to be displayed in forms"),
                                                                 ),
                                               ),
                                 ),
                     *s3_meta_fields())

        unique_question_names_per_template = settings.get_dc_unique_question_names_per_template()
        if unique_question_names_per_template:
            # Deduplicate Questions by Name/Template
            # - needed for importing multiple translations
            deduplicate = S3Duplicate(primary=("name", "template_id"))
        else:
            deduplicate = None

        configure(tablename,
                  onaccept = self.dc_question_onaccept,
                  deduplicate = deduplicate,
                  )

        # Reusable field
        represent = S3Represent(lookup=tablename)
        question_id = S3ReusableField("question_id", "reference %s" % tablename,
                                      label = T("Question"),
                                      represent = represent,
                                      requires = IS_ONE_OF(db, "dc_question.id",
                                                           represent,
                                                           ),
                                      sortby = "name",
                                      #comment = S3PopupLink(f="question",
                                      #                      tooltip=T("Add a new question"),
                                      #                      ),
                                      )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Question"),
            title_display = T("Question Details"),
            title_list = T("Questions"),
            title_update = T("Edit Question"),
            title_upload = T("Import Questions"),
            label_list_button = T("List Questions"),
            label_delete_button = T("Delete Question"),
            msg_record_created = T("Question added"),
            msg_record_modified = T("Question updated"),
            msg_record_deleted = T("Question deleted"),
            msg_list_empty = T("No Questions currently registered"))

        # Components
        add_components(tablename,
                       dc_question_l10n = "question_id",
                       )

        # =====================================================================
        # Question Translations
        #
        tablename = "dc_question_l10n"
        define_table(tablename,
                     question_id(),
                     s3_language(empty = False),
                     Field("name_l10n",
                           label = T("Translated Question"),
                           ),
                     Field("options_l10n", "json",
                           label = T("Translated Options"),
                           represent = lambda opts: ", ".join(json.loads(opts)),
                           requires = IS_EMPTY_OR(IS_JSONS3()),
                           ),
                     # @ToDo: Implement this when-required
                     Field("tooltip_l10n",
                           label = T("Translated Tooltip"),
                           ),
                     *s3_meta_fields())

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Translation"),
            title_display = T("Translation Details"),
            title_list = T("Translations"),
            title_update = T("Edit Translation"),
            title_upload = T("Import Translations"),
            label_list_button = T("List Translations"),
            label_delete_button = T("Delete Translation"),
            msg_record_created = T("Translation added"),
            msg_record_modified = T("Translation updated"),
            msg_record_deleted = T("Translation deleted"),
            msg_list_empty = T("No Translations currently registered"))

        configure(tablename,
                  onaccept = self.dc_question_l10n_onaccept,
                  )

        # =====================================================================
        # Pass names back to global scope (s3.*)
        return dict(dc_template_id = template_id,
                    )

    # -------------------------------------------------------------------------
    @staticmethod
    def defaults():
        """ Safe defaults for names in case the module is disabled """

        dummy = S3ReusableField("dummy_id", "integer",
                                readable = False,
                                writable = False,
                                )

        return dict(dc_template_id = lambda **attr: dummy("template_id"),
                    )

    # -------------------------------------------------------------------------
    @staticmethod
    def dc_template_create_onaccept(form):
        """
            On-accept routine for dc_template:
                - Create & link a Dynamic Table to use to store the Questions
        """

        form_vars = form.vars
        try:
            template_id = form_vars.id
        except AttributeError:
            return

        # Create the Dynamic Table
        settings = current.deployment_settings
        mobile_data = settings.get_dc_mobile_data()
        if settings.get_dc_mobile_inserts():
            table_settings = "" # Default
        else:
            table_settings = {"insertable": False}

        table_id = current.s3db.s3_table.insert(title = form_vars.get("name"),
                                                #mobile_form = False,
                                                mobile_data = mobile_data,
                                                settings = table_settings,
                                                )

        # Add a Field to link Answers together
        db = current.db
        db.s3_field.insert(table_id = table_id,
                           name = "response_id",
                           field_type = "reference dc_response",
                           #label = "Response",
                           require_not_empty = True,
                           component_key = True,
                           component_alias = "answer",
                           component_tab = True,
                           master = "dc_response",
                           settings = {"component_multiple": False},
                           )
        # @ToDo: Call onaccept if this starts doing anything other than just setting 'master'
        # @ToDo: Call set_record_owner() once we start restricting these

        # Link this Table to the Template
        db(db.dc_template.id == template_id).update(table_id=table_id)

    # -------------------------------------------------------------------------
    @staticmethod
    def dc_question_onaccept(form):
        """
            On-accept routine for dc_question:
                - Create & link a Dynamic Field to use to store the Question
        """

        try:
            question_id = form.vars.id
        except AttributeError:
            return

        db = current.db

        # Read the full Question
        qtable = db.dc_question
        question = db(qtable.id == question_id).select(qtable.id,
                                                       qtable.template_id,
                                                       qtable.field_id,
                                                       qtable.name,
                                                       qtable.comments,
                                                       qtable.field_type,
                                                       qtable.options,
                                                       qtable.require_not_empty,
                                                       limitby=(0, 1)
                                                       ).first()

        field_type = question.field_type
        options = None
        if field_type == 1:
            field_type = "string"
        elif field_type == 2:
            field_type = "integer"
        elif field_type == 4:
            field_type = "boolean"
        elif field_type == 5:
            T = current.T
            options = [T("Yes"),
                       T("No"),
                       T("Don't Know"),
                       ]
            field_type = "string"
        elif field_type == 6:
            options = question.options
            field_type = "string"
        elif field_type == 7:
            field_type = "date"
        elif field_type == 8:
            field_type = "datetime"
        elif field_type == 9:
            # Grid: Pseudo-question, no dynamic field
            return
        else:
            current.log.debug(field_type)
            raise NotImplementedError

        field_id = question.field_id
        if field_id:
            # Update the Dynamic Field
            db(current.s3db.s3_field.id == field_id).update(label = question.name,
                                                            field_type = field_type,
                                                            options = options,
                                                            #settings = settings,
                                                            require_not_empty = question.require_not_empty,
                                                            comments = question.comments,
                                                            )
            # @ToDo: Call onaccept if this starts doing anything other than just setting 'master'
        else:
            # Create the Dynamic Field
            # Lookup the table_id
            ttable = db.dc_template
            template = db(ttable.id == question.template_id).select(ttable.table_id,
                                                                    limitby=(0, 1)
                                                                    ).first()
            from uuid import uuid1
            name = "f%s" % str(uuid1()).replace("-", "_")
            field_id = current.s3db.s3_field.insert(table_id = template.table_id,
                                                    label = question.name,
                                                    name = name,
                                                    field_type = field_type,
                                                    options = options,
                                                    #settings = settings,
                                                    require_not_empty = question.require_not_empty,
                                                    comments = question.comments,
                                                    )
            # @ToDo: Call onaccept if this starts doing anything other than just setting 'master'
            # @ToDo: Call set_record_owner() once we start restricting these

            # Link the Field to the Question
            question.update_record(field_id=field_id)

    # -------------------------------------------------------------------------
    @staticmethod
    def dc_question_l10n_onaccept(form):
        """
            On-accept routine for dc_question_l10n:
                - Update the Translations file with translated Options
        """

        try:
            question_l10n_id = form.vars.id
        except AttributeError:
            return

        db = current.db

        # Read the Question
        qtable = db.dc_question
        ltable = db.dc_question_l10n
        query = (qtable.id == ltable.question_id) & \
                (ltable.id == question_l10n_id)
        question = db(query).select(qtable.field_type,
                                    qtable.options,
                                    ltable.options_l10n,
                                    ltable.language,
                                    limitby=(0, 1)
                                    ).first()

        if question["dc_question.field_type"] != 6:
            # Nothing we need to do
            return

        options = question["dc_question.options"]
        options_l10n = question["dc_question_l10n.options_l10n"]

        len_options = len(options)
        if len_options != len(options_l10n):
            current.session.error(T("Number of Translated Options don't match original!"))
            return

        # Read existing translations (if any)
        w2pfilename = os.path.join(current.request.folder, "languages",
                                   "%s.py" % question["dc_question_l10n.language"])

        if os.path.exists(w2pfilename):
            translations = read_dict(w2pfilename)
        else:
            translations = {}

        # Add ours
        for i in range(len_options):
            original = s3_str(options[i])
            translated = s3_str(options_l10n[i])
            if original != translated:
                translations[original] = translated

        # Write out new file
        write_dict(w2pfilename, translations)

# =============================================================================
class DataCollectionModel(S3Model):
    """
        Results of Assessments / Surveys
        - uses the Dynamic Tables back-end to store Answers
    """

    names = ("dc_target",
             "dc_target_id",
             "dc_response",
             "dc_response_id",
             )

    def model(self):

        T = current.T
        db = current.db

        add_components = self.add_components
        crud_strings = current.response.s3.crud_strings
        define_table = self.define_table

        location_id = self.gis_location_id
        template_id = self.dc_template_id

        # =====================================================================
        # Data Collection Target
        # - planning of Assessments / Surveys
        #   (optional step in the process)
        # - can be used to analyse a group of responses
        #
        tablename = "dc_target"
        define_table(tablename,
                     template_id(),
                     s3_date(default = "now"),
                     # Enable in-templates as-required
                     s3_language(readable = False,
                                 writable = False,
                                 ),
                     location_id(widget = S3LocationSelector(show_map = False,
                                                             show_postcode = False,
                                                             )),
                     #self.org_organisation_id(),
                     #self.pr_person_id(),
                     s3_comments(),
                     *s3_meta_fields())

        # Components
        add_components(tablename,

                       dc_response = "target_id",

                       event_event = {"link": "event_target",
                                      "joinby": "target_id",
                                      "key": "event_id",
                                      "actuate": "replace",
                                      },

                       hrm_training_event = {"link": "hrm_event_target",
                                             "joinby": "target_id",
                                             "key": "training_event_id",
                                             "multiple": False,
                                             "actuate": "replace",
                                             },
                       # Format for S3InlineComponent
                       hrm_event_target = {"joinby": "target_id",
                                           "multiple": False,
                                           }
                       )

        # CRUD strings
        crud_strings[tablename] = Storage(
            label_create = T("Create Data Collection Target"),
            title_display = T("Data Collection Target Details"),
            title_list = T("Data Collection Targets"),
            title_update = T("Edit Data Collection Target"),
            title_upload = T("Import Data Collection Targets"),
            label_list_button = T("List Data Collection Targets"),
            label_delete_button = T("Delete Data Collection Target"),
            msg_record_created = T("Data Collection Target added"),
            msg_record_modified = T("Data Collection Target updated"),
            msg_record_deleted = T("Data Collection Target deleted"),
            msg_list_empty = T("No Data Collection Targets currently registered"))

        target_id = S3ReusableField("target_id", "reference %s" % tablename,
                                    requires = IS_EMPTY_OR(
                                                IS_ONE_OF(db, "dc_target.id")
                                                ),
                                    readable = False,
                                    writable = False,
                                    )

        # =====================================================================
        # Answers / Responses
        # - instances of an Assessment / Survey
        # - each of these is a record in the Template's Dynamic Table
        #
        tablename = "dc_response"
        define_table(tablename,
                     self.super_link("doc_id", "doc_entity"),
                     target_id(),
                     template_id(),
                     s3_datetime(default = "now"),
                     # Enable in-templates as-required
                     s3_language(readable = False,
                                 writable = False,
                                 ),
                     location_id(),
                     self.org_organisation_id(),
                     self.pr_person_id(
                        default = current.auth.s3_logged_in_person(),
                     ),
                     s3_comments(),
                     *s3_meta_fields())

        # Configuration
        self.configure(tablename,
                       create_next = URL(f="respnse", args=["[id]", "answer"]),
                       # Question Answers are in a Dynamic Component
                       # - however they all have the same component name so add correct one in controller instead!
                       #dynamic_components = True,
                       super_entity = "doc_entity",
                       orderby = "dc_response.date desc",
                       )

        # CRUD strings
        label = current.deployment_settings.get_dc_response_label()
        if label == "Assessment":
            label = T("Assessment")
            crud_strings[tablename] = Storage(
                label_create = T("Create Assessment"),
                title_display = T("Assessment Details"),
                title_list = T("Assessments"),
                title_update = T("Edit Assessment"),
                title_upload = T("Import Assessments"),
                label_list_button = T("List Assessments"),
                label_delete_button = T("Delete Assessment"),
                msg_record_created = T("Assessment added"),
                msg_record_modified = T("Assessment updated"),
                msg_record_deleted = T("Assessment deleted"),
                msg_list_empty = T("No Assessments currently registered"))
        elif label == "Survey":
            label = T("Survey")
            crud_strings[tablename] = Storage(
                label_create = T("Create Survey"),
                title_display = T("Survey Details"),
                title_list = T("Surveys"),
                title_update = T("Edit Survey"),
                title_upload = T("Import Surveys"),
                label_list_button = T("List Surveys"),
                label_delete_button = T("Delete Survey"),
                msg_record_created = T("Survey added"),
                msg_record_modified = T("Survey updated"),
                msg_record_deleted = T("Survey deleted"),
                msg_list_empty = T("No Surveys currently registered"))
        else:
            label = T("Response")
            crud_strings[tablename] = Storage(
                label_create = T("Create Data Collection"),
                title_display = T("Data Collection Details"),
                title_list = T("Data Collections"),
                title_update = T("Edit Data Collection"),
                title_upload = T("Import Data Collections"),
                label_list_button = T("List Data Collections"),
                label_delete_button = T("Delete Data Collection"),
                msg_record_created = T("Data Collection added"),
                msg_record_modified = T("Data Collection updated"),
                msg_record_deleted = T("Data Collection deleted"),
                msg_list_empty = T("No Data Collections currently registered"))

        # @todo: representation including template name, location and date
        #        (not currently required since always hidden)
        represent = S3Represent(lookup=tablename,
                                fields=["date"],
                                )

        # Reusable field
        response_id = S3ReusableField("response_id", "reference %s" % tablename,
                                      label = label,
                                      represent = represent,
                                      requires = IS_ONE_OF(db, "dc_response.id",
                                                           represent,
                                                           ),
                                      comment = S3PopupLink(f="respnse",
                                                            ),
                                      )

        # Components
        add_components(tablename,
                       event_event = {"link": "event_response",
                                      "joinby": "response_id",
                                      "key": "event_id",
                                      "actuate": "replace",
                                      },
                       )

        # =====================================================================
        # Pass names back to global scope (s3.*)
        return dict(dc_response_id = response_id,
                    dc_target_id = target_id,
                    )

    # -------------------------------------------------------------------------
    @staticmethod
    def defaults():
        """ Safe defaults for names in case the module is disabled """

        dummy = S3ReusableField("dummy_id", "integer",
                                readable = False,
                                writable = False,
                                )

        return dict(dc_response_id = lambda **attr: dummy("response_id"),
                    dc_target_id = lambda **attr: dummy("target_id"),
                    )

# =============================================================================
def dc_rheader(r, tabs=None):
    """ Resource Headers for Data Collection Tool """

    if r.representation != "html":
        return None

    s3db = current.s3db
    tablename, record = s3_rheader_resource(r)
    if tablename != r.tablename:
        resource = s3db.resource(tablename, id=record.id)
    else:
        resource = r.resource

    rheader = None
    rheader_fields = []

    if record:
        T = current.T

        if tablename == "dc_template":

            tabs = ((T("Basic Details"), None),
                    (T("Sections"), "section"),
                    (T("Questions"), "question"),
                    )

            rheader_fields = (["name"],
                              )

        elif tablename == "dc_question":

            tabs = ((T("Basic Details"), None),
                    (T("Translations"), "question_l10n"),
                    )

            def options(record):
                if record.options:
                    return ", ".join(record.options)
                else:
                    return current.messages["NONE"]

            rheader_fields = ([(T("Question"), "name")],
                              [(T("Options"), options)],
                              ["comments"],
                              )

        elif tablename == "dc_response":

            tabs = ((T("Basic Details"), None, {"native": 1}),
                    (T("Answers"), "answer"),
                    (T("Attachments"), "document"),
                    )

            rheader_fields = [["template_id"],
                              ["location_id"],
                              ["date"],
                              ["person_id"],
                              ]

            db = current.db

            def contacts(record):
                ptable = s3db.pr_person
                ctable = s3db.pr_contact
                query = (ptable.id == record.person_id) & \
                        (ptable.pe_id == ctable.pe_id) & \
                        (ctable.deleted == False)
                data = db(query).select(ctable.value,
                                        ctable.contact_method,
                                        ctable.priority,
                                        orderby = ~ctable.priority,
                                        )
                if data:
                    # Prioritise Phone then Email
                    email = None
                    other = None
                    for contact in data:
                        if contact.contact_method == "SMS":
                            return contact.value
                        elif contact.contact_method == "Email":
                            if not email:
                                email = contact.value
                        else:
                            if not other:
                                other = contact.value
                    return email or other
                else:
                    # @ToDo: Provide an Edit button
                    return A(T("Add"))

            rheader_fields.append([(T("Contact Details"), contacts)])

            has_module = current.deployment_settings.has_module
            if has_module("stats"):
                # @ToDo: deployment_setting, not just presence of module
                def population(record):
                    ptable = s3db.stats_demographic
                    dtable = s3db.stats_demographic_data
                    date_field = dtable.date
                    value_field = dtable.value
                    query = (ptable.name == "Population") & \
                            (dtable.parameter_id == ptable.parameter_id) & \
                            (dtable.location_id == record.location_id) & \
                            (dtable.deleted == False)
                    data = db(query).select(value_field,
                                            date_field,
                                            limitby=(0, 1),
                                            orderby = ~date_field, # @ToDo: Handle case where system stores future predictions
                                            ).first()
                    if data:
                        return value_field.represent(data.value)
                    else:
                        return ""

                rheader_fields.insert(2, [(T("Total Population"), population)])

            if has_module("event"):
                etable = s3db.event_event
                ltable = s3db.event_response
                event_id = ltable.event_id
                date_field = etable.start_date
                query = (ltable.response_id == record.id) & \
                        (etable.id == event_id)
                event = db(query).select(etable.id,
                                         date_field,
                                         limitby=(0, 1)
                                         ).first()
                
                def event_name(record):
                    if event:
                        return event_id.represent(event.id)
                    else:
                        return ""

                def event_date(record):
                    if event:
                        return date_field.represent(event.start_date)
                    else:
                        return ""

                def event_days(record):
                    if event:
                        timedelta = record.date - event.start_date
                        return timedelta.days
                    else:
                        return ""

                rheader_fields.insert(0, [(event_id.label, event_name)])
                rheader_fields.insert(1, [(date_field.label, event_date)])
                # @ToDo: deployment_setting
                rheader_fields.insert(2, [(T("Number of Days since Event Occurred"), event_days)])

        elif tablename == "dc_target":

            label = current.deployment_settings.get_dc_response_label()
            if label == "Assessment":
                RESPONSES = T("Assessments")
            elif label == "Survey":
                RESPONSES = T("Surveys")
            else:
                RESPONSES = T("Responses")
        
            tabs = ((T("Basic Details"), None),
                    (RESPONSES, "response"),
                    )

            rheader_fields = (["template_id"],
                              ["location_id"],
                              ["date"],
                              )

        rheader = S3ResourceHeader(rheader_fields, tabs)(r,
                                                         table = resource.table,
                                                         record = record,
                                                         )

    return rheader

# =============================================================================
def dc_target_check(target_id):
    """
        Check whether a Survey has been Approved/Rejected & notify OM if not

        @param target_id: Target record_id

        @ToDo: Currently configured for IFRC Bangkok CCST...make this more
               generic if-required (e.g. Move this all to a deployment_setting)
    """

    T = current.T
    db = current.db
    s3db = current.s3db

    # Read Survey Record
    ttable = s3db.dc_target
    ltable = s3db.hrm_event_target
    etable = s3db.hrm_training_event
    query = (ttable.id == target_id)
    left = etable.on((ttable.id == ltable.target_id) & \
                     (etable.id == ltable.training_event_id))
    survey = db(query).select(ttable.approved_by,
                              ttable.deleted,
                              etable.name,
                              etable.location_id,
                              etable.start_date,
                              left = left,
                              limitby = (0, 1)
                              ).first()

    if not survey:
        return

    if survey["dc_target"].deleted:
        # Presumably it was Rejected
        return

    if survey["dc_target"].approved_by:
        # Survey was Approved
        return

    # List of recipients, grouped by language
    # Recipients: OM
    languages = {}

    utable = db.auth_user
    gtable = db.auth_group
    mtable = db.auth_membership
    ltable = s3db.pr_person_user
    query = (utable.id == mtable.user_id) & \
            (mtable.group_id == gtable.id) & \
            (gtable.uuid == "EVENT_OFFICE_MANAGER") & \
            (ltable.user_id == utable.id)
    users = db(query).select(ltable.pe_id,
                             utable.language,
                             )
    for user in users:
        language = user["auth_user.language"]
        if language in languages:
            languages[language].append(user["pr_person_user.pe_id"])
        else:
            languages[language] = [user["pr_person_user.pe_id"]]

    # Build Message
    event = survey["hrm_training_event"]
    event_date = event.start_date
    location_id = event.location_id
    url = "%s%s" % (current.deployment_settings.get_base_public_url(),
                    URL(c="dc", f="target", args=[target_id, "review"]),
                    )
    subject = T("Post-Event Survey hasn't been Approved/Rejected")
    message = T("The post-Event Survey for %(event_name)s on %(date)s in %(location)s has not been Approved or Rejected") % \
            dict(date = "%(date)s", # Localise per-language
                 event_name = event.name,
                 location = "%(location)s", # Localise per-language
                 #url = url,
                 )

    # Send Localised Mail(s)
    send_email = current.msg.send_by_pe_id
    session_s3 = current.session.s3
    date_represent = S3DateTime.date_represent # We want Dates not datetime which etable.start_date uses
    location_represent = s3db.gis_LocationRepresent()
    for language in languages:
        T.force(language)
        subject = s3_str(subject)
        session_s3.language = language # for date_represent
        message = s3_str(message % dict(date = date_represent(event_date),
                                        location = location_represent(location_id),
                                        ),
                         )
        users = languages[language]
        for pe_id in users:
            send_email(pe_id,
                       subject = subject,
                       message = message,
                       )

    # NB No need to restore UI language as this is run as an async task w/o UI
    return

# END =========================================================================
