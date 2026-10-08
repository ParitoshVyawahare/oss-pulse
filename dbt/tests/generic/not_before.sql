{#-
    Generic column test: a milestone timestamp must never be earlier than another one
    (e.g. a PR cannot be merged before it was opened). Nulls are allowed: a milestone
    that has not happened yet is fine.
-#}
{% test not_before(model, column_name, other_column) %}

select *
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} < {{ other_column }}

{% endtest %}
