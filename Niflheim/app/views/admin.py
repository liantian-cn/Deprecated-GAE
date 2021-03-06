#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# __author__ = 'Liantian'
# __email__ = "liantian.me+code@gmail.com"
#
# MIT License
#
# Copyright (c) 2018 liantian
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import mimetypes
import os
import urllib
from datetime import datetime

import cloudstorage
from flask import flash
from flask import render_template, request, redirect, url_for, jsonify
from google.appengine.api import app_identity
from google.appengine.api import images
from google.appengine.api import memcache
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from slugify import slugify

from forms import EditPostForm, SiteOptionForm, NewPostForm, NewCategoryForm
from main import app
from models import Post, Category


# from models import Comment


@app.route('/delay_redirect/', methods=['GET'], endpoint="delay_redirect")
def delay_redirect():
    url = request.args.get('url')
    return render_template('admin/delay_redirect.html', url=url)


def go_delay_redirect(url):
    base = url_for("delay_redirect")
    query = urllib.quote(url)

    return redirect("{0}?url={1}".format(base, query))


@app.route('/admin/base', methods=['GET'], endpoint="admin.index")
def admin_index():
    return render_template('admin/base.html')


@app.route('/admin/option/', methods=['GET', 'POST'], endpoint="admin.option")
def edit_option():
    form = SiteOptionForm()
    if form.validate_on_submit():
        form.save()
        memcache.delete(key='SITE_OPTIONS')
        flash(u'??????????????????')
        return go_delay_redirect(url_for("admin.index"))
    return render_template('admin/option.html', form=form)


@app.route('/admin/post/<key>/edit/', methods=['GET', 'POST'], endpoint="admin.post.edit")
def edit_post(key):
    post = ndb.Key(urlsafe=key).get()
    form = EditPostForm(obj=post)
    if form.validate_on_submit():
        form.save()
        flash(u'??????????????????')
        return go_delay_redirect(url_for("admin.post.edit", key=key))
    return render_template('admin/new_or_edit_post.html',
                           form=form,
                           post=post,
                           new=False)


@app.route('/admin/post/new/', methods=['GET', 'POST'], endpoint="admin.post.new")
def new_post():
    form = NewPostForm()
    if form.validate_on_submit():
        form.save()
        flash(u'??????????????????')
        return go_delay_redirect(url_for("admin.index"))
    return render_template('admin/new_or_edit_post.html',
                           form=form,
                           new=True)


@app.route('/admin/post/list/', methods=['GET'], endpoint="admin.post.list")
def list_post():
    page_size = app.config.get("SITE_ADMIN_POST_PER_PAGE", 20)
    cursor = request.args.get('cursor')
    start_cursor = Cursor(urlsafe=request.args.get('cursor'))
    posts, next_cursor, more = Post.query().order(-Post.modified).fetch_page(page_size=page_size, start_cursor=start_cursor)
    return render_template('admin/list_post.html',
                           posts=posts,
                           next_cursor=next_cursor,
                           cursor=cursor,
                           more=more)


@app.route('/admin/category/', methods=['GET', 'POST'], endpoint="admin.category.list")
def list_category():
    form = NewCategoryForm()
    parent = request.args.get('parent')
    if parent is None:
        categories = Category.query(Category.parent == None).fetch()
    else:
        parent_key = ndb.Key(urlsafe=parent)
        categories = Category.query(Category.parent == parent_key).fetch()
        form.parent.data = parent

    if form.validate_on_submit():
        form.save()
        flash(u'??????????????????')
        if (form.parent.data.strip() is "") or (form.parent.data.strip() is u""):
            return go_delay_redirect(url_for("admin.category.list"))
        else:
            return go_delay_redirect("{0}?parent={1}".format(url_for("admin.category.list"), form.parent.data.strip()))

    return render_template('admin/category.html',
                           categories=categories,
                           parent=parent,
                           form=form)


@app.route('/admin/category/<key>/delete/', methods=['GET'], endpoint="admin.category.delete")
def delete_category(key):
    self_key = ndb.Key(urlsafe=key)

    key_list = [child_key for child_key in Category.query(Category.parent == self_key).fetch(keys_only=True)]
    key_list.append(self_key)
    for post in Post.query(Post.category.IN(key_list)).fetch():
        post.category = None
        post.put()

    ndb.delete_multi(key_list)

    return go_delay_redirect(url_for("admin.category.list"))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in set(app.config.get("SITE_ALLOWED_EXTENSIONS").split(","))


@app.route('/admin/editormd_image_upload/', methods=['POST', "GET"], endpoint="admin.editormd_image_upload")
def editormd_image_upload():
    mimetypes.init()
    if 'editormd-image-file' not in request.files:
        return jsonify({"success": 0, "message": u"No file part"})
    file = request.files['editormd-image-file']
    if file.filename == '':
        return jsonify({"success": 0, "message": u"No selected file"})
    if file and allowed_file(file.filename):
        directory = "upload/{0}".format(datetime.now().strftime("%Y%m%d/%H"))
        bucket_name = os.environ.get(
            'BUCKET_NAME', app_identity.get_default_gcs_bucket_name())
        bucket = '/' + bucket_name
        filename = "{0}/{3}/{1}.{2}".format(bucket, slugify(file.filename.rsplit('.', 1)[0]).replace("-", "_"), file.filename.rsplit('.', 1)[1], directory)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        write_retry_params = cloudstorage.RetryParams(backoff_factor=1.1)
        gcs_file = cloudstorage.open(filename,
                                     'w',
                                     content_type=content_type,
                                     options={'x-goog-acl': 'public-read'},
                                     retry_params=write_retry_params)
        gcs_file.write(file.read())
        gcs_file.close()
        gs = "/gs{0}".format(filename)
        blob_key = blobstore.create_gs_key(gs)
        url = images.get_serving_url(blob_key, size=app.config["SITE_POST_IMG_WIDTH"], crop=False, secure_url=True)
        return jsonify({"success": 1, "message": u"No allowed_file", "url": url})

    return jsonify({"success": 0, "message": u"No allowed_file"})
