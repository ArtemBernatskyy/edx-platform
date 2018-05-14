// Generated by CoffeeScript 1.6.1
(function() {
  var MathJaxProcessor;

  MathJaxProcessor = (function() {
    var CODESPAN, MATHSPLIT;

    MATHSPLIT = /(\$\$?|\\(?:begin|end)\{[a-z]*\*?\}|\\[\\{}$]|[{}]|(?:\n\s*)+|@@\d+@@)/i;

    CODESPAN = /(^|[^\\])(`+)([^\n]*?[^`\n])\2(?!`)/gm;

    function MathJaxProcessor(inlineMark, displayMark) {
      this.inlineMark = inlineMark || "$";
      this.displayMark = displayMark || "$$";
      this.math = null;
      this.blocks = null;
    }

    MathJaxProcessor.prototype.processMath = function(start, last, preProcess) {
      var block, i, _i, _ref;
      block = this.blocks.slice(start, last + 1).join("").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (MathJax.Hub.Browser.isMSIE) {
        block = block.replace(/(%[^\n]*)\n/g, "$1<br/>\n");
      }
      for (i = _i = _ref = start + 1; _ref <= last ? _i <= last : _i >= last; i = _ref <= last ? ++_i : --_i) {
        this.blocks[i] = "";
      }
      this.blocks[start] = "@@" + this.math.length + "@@";
      if (preProcess) {
        block = preProcess(block);
      }
      return this.math.push(block);
    };

    MathJaxProcessor.prototype.removeMath = function(text) {
      var block, braces, current, deTilde, end, hasCodeSpans, last, start, _i, _ref;
      text = text || "";
      this.math = [];
      start = end = last = null;
      braces = 0;
      hasCodeSpans = /`/.test(text);
      if (hasCodeSpans) {
        text = text.replace(/~/g, "~T").replace(CODESPAN, function($0) {
          return $0.replace(/\$/g, "~D");
        });
        deTilde = function(text) {
          return text.replace(/~([TD])/g, function($0, $1) {
            return {
              T: "~",
              D: "$"
            }[$1];
          });
        };
      } else {
        deTilde = function(text) {
          return text;
        };
      }
      this.blocks = _split(text.replace(/\r\n?/g, "\n"), MATHSPLIT);
      for (current = _i = 1, _ref = this.blocks.length; _i < _ref; current = _i += 2) {
        block = this.blocks[current];
        if (block.charAt(0) === "@") {
          this.blocks[current] = "@@" + this.math.length + "@@";
          this.math.push(block);
        } else if (start) {
          if (block === end) {
            if (braces) {
              last = current;
            } else {
              this.processMath(start, current, deTilde);
              start = end = last = null;
            }
          } else if (block.match(/\n.*\n/)) {
            if (last) {
              current = last;
              this.processMath(start, current, deTilde);
            }
            start = end = last = null;
            braces = 0;
          } else if (block === "{") {
            ++braces;
          } else if (block === "}" && braces) {
            --braces;
          }
        } else {
          if (block === this.inlineMark || block === this.displayMark) {
            start = current;
            end = block;
            braces = 0;
          } else if (block.substr(1, 5) === "begin") {
            start = current;
            end = "\\end" + block.substr(6);
            braces = 0;
          }
        }
      }
      if (last) {
        this.processMath(start, last, deTilde);
        start = end = last = null;
      }
      return deTilde(this.blocks.join(""));
    };

    MathJaxProcessor.removeMathWrapper = function(_this) {
      return function(text) {
        return _this.removeMath(text);
      };
    };

    MathJaxProcessor.prototype.replaceMath = function(text) {
      var _this = this;
      text = text.replace(/@@(\d+)@@/g, function($0, $1) {
        return _this.math[$1];
      });
      this.math = null;
      return text;
    };

    MathJaxProcessor.replaceMathWrapper = function(_this) {
      return function(text) {
        return _this.replaceMath(text);
      };
    };

    return MathJaxProcessor;

  })();

  if (typeof Markdown !== "undefined" && Markdown !== null) {
    Markdown.getMathCompatibleConverter = function(postProcessor) {
      var converter, processor;
      postProcessor || (postProcessor = (function(text) {
        return text;
      }));
      converter = Markdown.getSanitizingConverter();
      if (typeof MathJax !== "undefined" && MathJax !== null) {
        processor = new MathJaxProcessor();
        converter.hooks.chain("preConversion", MathJaxProcessor.removeMathWrapper(processor));
        converter.hooks.chain("postConversion", function(text) {
          return postProcessor(MathJaxProcessor.replaceMathWrapper(processor)(text));
        });
      }
      return converter;
    };
    Markdown.makeWmdEditor = function(elem, appended_id, imageUploadUrl, postProcessor) {
      var $elem, $wmdPanel, $wmdPreviewContainer, ajaxFileUpload, converter, delayRenderer, editor, imageUploadHandler, initialText, wmdInputId, _append;
      $elem = $(elem);
      if (!$elem.length) {
        console.log("warning: elem for makeWmdEditor doesn't exist");
        return;
      }
      if (!$elem.find(".wmd-panel").length) {
        initialText = $elem.html();
        $elem.empty();
        _append = appended_id || "";
        wmdInputId = "wmd-input" + _append;
        $wmdPreviewContainer = $("<div>").addClass("wmd-preview-container").attr("role", "region").attr("aria-label", gettext("HTML preview of post")).append($("<div>").addClass("wmd-preview-label").text(gettext("Preview"))).append($("<div>").attr("id", "wmd-preview" + _append).addClass("wmd-panel wmd-preview"));
        $wmdPanel = $("<div>").addClass("wmd-panel").append($("<div>").attr("id", "wmd-button-bar" + _append)).append($("<label>").addClass("sr").attr("for", wmdInputId).text(gettext("Post body"))).append($("<textarea>").addClass("wmd-input").attr("id", wmdInputId).html(initialText)).append($wmdPreviewContainer);
        $elem.append($wmdPanel);
      }
      converter = Markdown.getMathCompatibleConverter(postProcessor);
      ajaxFileUpload = function(imageUploadUrl, input, startUploadHandler) {
        $("#loading").ajaxStart(function() {
          return $(this).show();
        }).ajaxComplete(function() {
          return $(this).hide();
        });
        $("#upload").ajaxStart(function() {
          return $(this).hide();
        }).ajaxComplete(function() {
          return $(this).show();
        });
        return $.ajaxFileUpload({
          url: imageUploadUrl,
          secureuri: false,
          fileElementId: 'file-upload',
          dataType: 'json',
          success: function(data, status) {
            var error, fileURL;
            fileURL = data['result']['file_url'];
            error = data['result']['error'];
            if (error !== '') {
              alert(error);
              if (startUploadHandler) {
                $('#file-upload').unbind('change').change(startUploadHandler);
              }
              return console.log(error);
            } else {
              return $(input).val(fileURL);
            }
          },
          error: function(data, status, e) {
            alert(e);
            if (startUploadHandler) {
              return $('#file-upload').unbind('change').change(startUploadHandler);
            }
          }
        });
      };
      imageUploadHandler = function(elem, input) {
        return ajaxFileUpload(imageUploadUrl, input, imageUploadHandler);
      };
      editor = new Markdown.Editor(converter, appended_id, null, imageUploadHandler);
      delayRenderer = new MathJaxDelayRenderer();
      editor.hooks.chain("onPreviewPush", function(text, previewSet) {
        return delayRenderer.render({
          text: text,
          previewSetter: previewSet
        });
      });
      editor.run();
      return editor;
    };
  }

}).call(this);
