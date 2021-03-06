from django.contrib.auth.models import User
from django import forms
from django.utils.translation import ugettext_lazy as _
from PIL import Image
import os, datetime
from django.conf import settings
from django.template import Template, Context
from core.models import UserProfile, Reservation, EmailTemplate, Room, Location, LocationMenu, Reservable
from django.contrib.sites.models import Site
import re
import base64
import uuid

from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class UserProfileForm(forms.ModelForm):     
	# this is used in the profile edit page. 
	''' This form manually incorporates the fields corresponding to the base 
	User model, associated via the UserProfile model via a OneToOne field, so 
	that both models can be updated via the same form. '''

	error_messages = {
		'password_mismatch': _("The two password fields didn't match."),
	}

	#username = forms.CharField(widget=forms.HiddenInput(attrs={'required': 'false'}))
	first_name = forms.CharField(label=_('First Name'), widget= forms.TextInput(attrs={'class':'form-control', 'required': 'true', 'placeholder': 'first name'}))
	last_name = forms.CharField(label=_('Last Name'), widget= forms.TextInput(attrs={'class':'form-control', 'required': 'true', 'placeholder': 'last name'}))
	email = forms.EmailField(label=_("E-mail"), max_length=75, widget= forms.TextInput(attrs={'class':'form-control', 'required': 'true', 'placeholder': 'email'}))
	password1 = forms.CharField(widget=forms.PasswordInput(render_value=False, attrs={'class':'form-control', 'required': 'true', 'placeholder': 'password'}), label=_("New Password"))
	password2 = forms.CharField(widget=forms.PasswordInput(render_value=False, attrs={'class':'form-control', 'required': 'true', 'placeholder': 'password (again)'}), label=_("New Password (again)"))
	cropped_image_data = forms.CharField(widget=forms.HiddenInput())

	class Meta:
		model = UserProfile
		exclude = ['user', 'status', 'image_thumb', 'customer_id', 'last4']
		# fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2', 'image', 'bio', 'links']
		widgets = {
			'bio': forms.Textarea(attrs={'class':'form-control', 'rows': '2', 'required': 'true'}),
			'links': forms.TextInput(attrs={'class':'form-control'}),
			'projects': forms.Textarea(attrs={'class':'form-control', 'rows': '2', 'required': 'true'}),
			'sharing': forms.Textarea(attrs={'class':'form-control', 'rows': '2', 'required': 'true'}),
			'discussion': forms.Textarea(attrs={'class':'form-control', 'rows': '2', 'required': 'true'}),
			'referral': forms.TextInput(attrs={'class':'form-control', 'required': 'true', 'placeholder': 'referral'}),
			'city': forms.TextInput(attrs={'class':'form-control', 'required': 'true', 'placeholder': 'city'}),
		}

	def __init__(self, *args, **kwargs):
		super(UserProfileForm, self).__init__(*args, **kwargs)

		# self.instance will always be an instance of UserProfile. if this
		# is an existing object, then populate the initial values. 
		if self.instance.id is not None:
			# initialize the form fields with the existing values from the model.  	
			self.fields['first_name'].initial = self.instance.user.first_name
			self.fields['last_name'].initial = self.instance.user.last_name
			
			#self.fields['username'].initial = self.instance.user.username
			# Since validation isn't working, make this readonly for now -JLS
			#self.fields['email'] = forms.EmailField(widget=forms.TextInput(attrs={'class':'form-control', 'readonly':True}))
			self.fields['email'].initial = self.instance.user.email	
			self.fields['cropped_image_data'].required = False
			
			self.fields['password1'] = forms.CharField(widget=forms.PasswordInput(render_value=False, attrs={'class':'form-control', 'placeholder':'password'}), label=_("New Password"))
			self.fields['password1'].required = False
			self.fields['password2'] = forms.CharField(widget=forms.PasswordInput(render_value=False, attrs={'class':'form-control', 'placeholder':'password'}), label=_("New Password (again)"))
			self.fields['password2'].required = False

	def clean_password2(self):
		password1 = self.cleaned_data.get('password1')
		password2 = self.cleaned_data.get('password2')
		if password1 and password2:
			if password1 != password2:
				raise forms.ValidationError(
					self.error_messages['password_mismatch'])
		return password2

	def clean_email(self):
		email = self.cleaned_data['email']
		if not self.instance.id:
			if email and User.objects.filter(email=email):
				raise forms.ValidationError('There is already a user with this email. If this is your account and you need to recover your password, you can do so from the login page.')
		return email

	def create_username(self, suffix=""):
		clean_first = self.cleaned_data['first_name'].strip().lower()
		clean_last = self.cleaned_data['last_name'].strip().lower()
		username = "%s_%s%s" % (clean_first, clean_last, suffix)
		clean_username = username.replace(" ", "_")
		clean_username = clean_username.replace(".", "_")
		clean_username = clean_username.replace("@", "")
		clean_username = clean_username.replace("+", "")
		clean_username = clean_username.replace("-", "")
		clean_username = clean_username.replace("'", "")
		return clean_username

	def clean(self):
		if not 'username' in self.cleaned_data:
			# Generate a unique username
			tries = 1
			username = self.create_username()
			while User.objects.filter(username=username).count() > 0:
				tries = tries + 1
				username = self.create_username(suffix=tries)
			self.cleaned_data['username'] = username
			
		try:
			img_data = self.cleaned_data['cropped_image_data']
			# If none or len 0, means illegal image data
			if (img_data == False or img_data == None or len(img_data) == 0):
				#raise Exception('There was no image provided')
				# Image data on creation is insured by the javascript validator.
				# If we don't have image data here it's because we don't need to 
				# update the image.  Doing nothing -- JLS
				return
		except:
			raise forms.ValidationError('No valid image was provided.')

		# Decode the image data
		img_data = base64.b64decode(img_data)
		filename = "%s.png" % uuid.uuid4()

		# XXX make the upload path a fixed setting in models, since it's
		# reference in three places
		upload_path = "data/avatars/%s/" % self.cleaned_data['username']
		upload_abs_path = os.path.join(settings.MEDIA_ROOT, upload_path)
		if not os.path.exists(upload_abs_path):
			os.makedirs(upload_abs_path)
		full_file_name = os.path.join(upload_abs_path, filename)

		with open(full_file_name, 'wb') as f:
			f.write(img_data)
			f.close()
		self.cleaned_data['image'] = full_file_name
		return 

	def clean_links(self):
		# validates and formats the urls, returning a string of comma-separated urls
		links = self.cleaned_data['links']
		if len(links) > 0:
			raw_link_list = links.split(',')
			# the UrlField class has some lovely validation code written already.  
			url = forms.URLField()
			cleaned_links = []
			for l in raw_link_list:
				try:
					cleaned = url.clean(l.strip())
					cleaned_links.append(cleaned)
				except forms.ValidationError:
					# customize the error raised by UrlField.
					raise forms.ValidationError('At least one of the URLs is not correctly formatted.')
			links = ", ".join(cleaned_links)
		return links

	def create_user(self):
		"Creates the User object"
		if not self.is_valid():
			raise Exception('The form must be valid in order to save')

		first = self.cleaned_data['first_name'].strip().title()
		if len(first) == 0:
			raise forms.ValidationError("First Name Required.")
		last = self.cleaned_data['last_name'].strip().title()
		if len(last) == 0:
			raise forms.ValidationError("Last Name Required.")
		email = self.cleaned_data['email'].strip().lower()
		if len(email) == 0:
			raise forms.ValidationError("Email Required.")
		if User.objects.filter(email=email).count() > 0:
			raise forms.ValidationError("Email address '%s' already in use." % email)
		
		# Username generated in clean method
		username = self.cleaned_data['username']
	
		user = User(username=username, first_name=first, last_name=last, email=email)
		password = self.clean_password2()
		user.set_password(password)
		user.save()
		return user

	def save(self, commit=True):
		# save the UserProfile (if editing an existing instance, it will be updated)
		profile = super(UserProfileForm, self).save(commit=False)
		# then update the User model with the values provided
		try: 
			# Editing 
			user = User.objects.get(pk=profile.user.pk)
			if self.cleaned_data.get('email'):
				user.email = self.cleaned_data.get('email')
			if self.cleaned_data['first_name']:
				user.first_name = self.cleaned_data.get('first_name')
			if self.cleaned_data['last_name']:
				user.last_name = self.cleaned_data.get('last_name')
			if self.cleaned_data.get('password2'):
				# set_password hashes the selected password
				user.set_password(self.cleaned_data['password2'])
			user.save()
		except:
			# Adding
			user = self.create_user()
			profile.user = user

		profile.save()
		return user

class LocationSettingsForm(forms.ModelForm):
	class Meta:
		model = Location
		# Not sure about Timezones and Bank Information.  Not including for now - JLS
		fields = ['name', 'slug', 'address', 'latitude', 'longitude',  'max_reservation_days', 'welcome_email_days_ahead', 'house_access_code',
					'ssid', 'ssid_password', 'email_subject_prefix', 'check_out', 'check_in', 'public']
		widgets = {
			'name': forms.TextInput(attrs={'class':'form-control', 'size': '32'}),
			'slug': forms.TextInput(attrs={'class':'form-control', 'size': '16'}),
			'address': forms.TextInput(attrs={'class':'form-control', 'size': '64'}),
			'latitude': forms.TextInput(attrs={'class':'form-control', 'size': '16'}),
			'longitude': forms.TextInput(attrs={'class':'form-control', 'size': '16'}),
			'max_reservation_days': forms.TextInput(attrs={'class':'form-control', 'size': '16'}),
			'welcome_email_days_ahead': forms.TextInput(attrs={'class':'form-control', 'size': '8'}),
			'house_access_code': forms.TextInput(attrs={'class':'form-control', 'size': '32'}),
			'ssid': forms.TextInput(attrs={'class':'form-control', 'size': '32'}),
			'ssid_password': forms.TextInput(attrs={'class':'form-control', 'size': '32'}),
			'email_subject_prefix': forms.TextInput(attrs={'class':'form-control', 'size': '32'}),
			'check_out': forms.TextInput(attrs={'class':'form-control', 'size': '8'}),
			'check_in': forms.TextInput(attrs={'class':'form-control', 'size': '8'}),
		}
		
class LocationUsersForm(forms.ModelForm):
	class Meta:
		model = Location
		fields = ['house_admins', ]

class LocationContentForm(forms.ModelForm):
	class Meta:
		model = Location
		fields = ['short_description', 'stay_page', 'announcement', 'front_page_stay', 'front_page_participate', 'image']
		widgets = {
			'short_description': forms.Textarea(attrs={'class':'form-control', 'rows': '16', 'cols': '100', 'required': 'true'}),
			'stay_page': forms.Textarea(attrs={'class':'form-control', 'rows': '16', 'cols': '100', 'required': 'true'}),
			'announcement': forms.Textarea(attrs={'class':'form-control', 'rows': '16', 'cols': '100', 'required': 'true'}),
			'front_page_stay': forms.Textarea(attrs={'class':'form-control', 'rows': '16', 'cols': '100', 'required': 'true'}),
			'front_page_participate': forms.Textarea(attrs={'class':'form-control', 'rows': '16', 'cols': '100', 'required': 'true'}),
		}

class BootstrapModelForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super(BootstrapModelForm, self).__init__(*args, **kwargs)
		for field_name, field in self.fields.items():
			field.widget.attrs['class'] = 'form-control'

class LocationMenuForm(BootstrapModelForm):
	class Meta:
		model = LocationMenu
		exclude = ['location',]
		widgets = { 
			'name': forms.TextInput(attrs={'class':'form-control', 'size': '32'}),
		}

class LocationPageForm(forms.Form):
	def __init__(self, *args, **kwargs):
		location = kwargs.pop('location', None)
		super(LocationPageForm, self).__init__(*args, **kwargs)
		if location:
			self.fields['menu'].queryset = LocationMenu.objects.filter(location=location)
	
	menu = forms.ModelChoiceField(queryset=None, empty_label=None)
	slug = forms.CharField(widget=forms.TextInput(attrs={'class':'form-control', 'size': '32'}))
	title = forms.CharField(widget=forms.TextInput(attrs={'class':'form-control', 'size': '32'}))
	content = forms.CharField(widget=forms.Textarea(attrs={'class':'form-control', 'rows': '16', 'cols': '72', 'required': 'true'}))

class LocationRoomForm(BootstrapModelForm):
	class Meta:
		model = Room
		exclude = ['location',]
		widgets = { 
			'description': forms.Textarea(attrs={'rows': '3'}),
		}

class LocationReservableForm(BootstrapModelForm):
	class Meta:
		model = Reservable
		exclude = ['room',]
		widgets = { 
			'start_date': forms.DateInput(attrs={'class':'datepicker'}),
			'end_date': forms.DateInput(attrs={'class':'datepicker'}),
		}

class ReservationForm(forms.ModelForm):
	class Meta:
		model = Reservation
		exclude = ['created', 'updated', 'user', 'last_msg', 'status', 'location', 'tags', 'rate', 'suppressed_fees', 'bill']
		widgets = { 
			'arrive': forms.DateInput(attrs={'class':'datepicker form-control form-group'}),
			'depart': forms.DateInput(attrs={'class':'datepicker form-control form-group'}),
			'arrival_time': forms.TextInput(attrs={'class':'form-control form-group'}),
			'room': forms.Select(attrs={'class':'form-control form-group'}),
			'purpose': forms.TextInput(attrs={'class':'form-control form-group'}),
			'comments': forms.Textarea(attrs={'class':'form-control form-group'}),
		}

	def __init__(self, location, *args, **kwargs):
		super(ReservationForm, self).__init__(*args, **kwargs)
		if not location:
			raise Exception("No location given!")
		self.location = location
		self.fields['room'].queryset = self.location._rooms_with_future_reservability_queryset()

	def clean(self):
		cleaned_data = super(ReservationForm, self).clean()
		arrive = cleaned_data.get('arrive')
		depart = cleaned_data.get('depart')
		if (depart - arrive).days > self.location.max_reservation_days:
			self._errors["depart"] = self.error_class(['Sorry! We only accept reservation requests greater than 2 weeks in special circumstances. Please limit your request to two weeks.'])
		return cleaned_data

	# XXX TODO
	# make sure depart is at least one day after arrive. 

class AdminReservationForm(forms.ModelForm):
	class Meta:
		model = Reservation
		exclude = ['created', 'updated', 'user', 'last_msg', 'status', 'location', 'tags', 'rate', 'suppressed_fees', 'bill']


class PaymentForm(forms.Form):
	name = forms.CharField(widget=forms.TextInput(attrs={'class':"form-control"}))
	email = forms.EmailField(widget=forms.TextInput(attrs={'class':"form-control", 'type': 'email'}))
	card_number = forms.CharField(widget=forms.TextInput(attrs={'class':"form-control"}))
	cvc = forms.IntegerField(widget=forms.TextInput(attrs={'class':"form-control", 'type': 'number'}))
	expiration_month = forms.IntegerField(label='(MM)', widget=forms.TextInput(attrs={'class':"form-control", 'type': 'number'}))
	expiration_year = forms.IntegerField(label='(YYYY)', widget=forms.TextInput(attrs={'class':"form-control", 'type': 'number'}))
	amount = forms.FloatField(label="Amount", widget=forms.TextInput(attrs={'class':"form-control inline", 'type': 'number', 'min': '0', 'step': '0.01'}))
	comment = forms.CharField(widget=forms.Textarea(attrs={'class':"form-control"}), required=False)

	def __init__ (self, *args, **kwargs):
		# have to call super first, which initializes the 'fields' dictionary

		try:
			default_amount = kwargs.pop('default_amount')
		except:
			default_amount = None
		super(PaymentForm, self).__init__(*args, **kwargs)
		if default_amount:
			self.fields['amount'].initial = default_amount


class StripeCustomerCreationForm(forms.Form):
	name = forms.CharField()
	email = forms.EmailField()
	card_number = forms.CharField()
	cvc = forms.IntegerField()
	expiration_month = forms.IntegerField(label='(MM)')
	expiration_year = forms.IntegerField(label='(YYYY)')


class EmailTemplateForm(forms.Form):
	''' We don't actually make this a model form because it's a derivative
	function of a model but not directly constructed from the model fields
	itself.''' 
	sender = forms.EmailField(widget=forms.TextInput(attrs={'readonly':'readonly', 'class':"form-control"}))
	recipient = forms.EmailField(widget=forms.TextInput(attrs={'class':"form-control"}))
	footer = forms.CharField( widget=forms.Textarea(attrs={'readonly':'readonly', 'class':"form-control"}))
	subject = forms.CharField(widget=forms.TextInput(attrs={'class':"form-control"}))
	body = forms.CharField(widget=forms.Textarea(attrs={'class':"form-control"}))

	def __init__(self, tpl, reservation, location):
		''' pass in an EmailTemplate instance, and a reservation object '''

		domain = Site.objects.get_current().domain
		# calling super will initialize the form fields 
		super(EmailTemplateForm, self).__init__()

		# add in the extra fields
		self.fields['sender'].initial = location.from_email()
		self.fields['recipient'].initial = "%s, %s" % (reservation.user.email, location.from_email())
		self.fields['footer'].initial = forms.CharField(
				widget=forms.Textarea(attrs={'readonly':'readonly'})
			)
		self.fields['footer'].initial = '''--------------------------------\nYour reservation is from %s to %s.\nManage your reservation at https://%s%s.''' % (reservation.arrive, reservation.depart, domain, reservation.get_absolute_url())

		# both the subject and body fields expect to have access to all fields
		# associated with a reservation, so all reservation model fields are
		# passed to the template renderer, even though we don't know (and so
		# that we don't have to know) which specific fields a given template
		# wants to use). 
		
		template_variables = {
			'created': reservation.created,
			'updated': reservation.updated,
			'status': reservation.status,
			'user': reservation.user,
			'arrive': reservation.arrive, 
			'depart': reservation.depart, 
			'arrival_time': reservation.arrival_time,
			'room': reservation.room, 
			'num_nights': reservation.total_nights(), 
			'purpose': reservation.purpose,
			'comments': reservation.comments,
			'welcome_email_days_ahead': location.welcome_email_days_ahead,
			'reservation_url': "https://"+domain+reservation.get_absolute_url()
		}

		self.fields['subject'].initial = '['+location.email_subject_prefix+'] ' + Template(tpl.subject).render(Context(template_variables)) + ' (#' + str(reservation.id) + ')'
		self.fields['body'].initial = Template(tpl.body).render(Context(template_variables))


