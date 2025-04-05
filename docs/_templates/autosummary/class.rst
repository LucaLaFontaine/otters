..
  class.rst

{{ name | escape | underline }}

.. currentmodule:: {{ module }}

.. autoclass:: {{ objname }}
    :members:
    :show-inheritance:
    :inherited-members:

    {% block methods %}
        {% if methods %}
            .. rubric:: {{ _('Methods') }}

            .. autosummary::
                :toctree:
                :nosignatures:
                {% for item in methods %}
                    ~{{ name }}.{{ item }}
                {%- endfor %}
        {% endif %}
    {% endblock %}